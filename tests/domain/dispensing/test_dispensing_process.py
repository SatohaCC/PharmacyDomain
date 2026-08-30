"""調剤セッション集約のテスト。

主眼は「集約が単独で判定できることだけを ``validate()`` に置いた」ことの検証で、
処方箋や前回調剤を要する検証はここには**現れない**。
それらは Domain Service のテストが担う。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.dispensing import (
    AuditTimestamp,
    CancellationReasonMismatchError,
    DispensedMedicineRequiredError,
    DispensedRpRequiredError,
    DispensingCancellationReason,
    DispensingCompletionType,
    DispensingIterationOutOfRangeError,
    DispensingProcessStatus,
    DispensingSplitReason,
    DispensingStatusTransitionError,
    DuplicatedDispensedLineNumberError,
    DuplicatedDispensedRpNumberError,
    DuplicatedPreparationMethodError,
    NextDispensingDate,
    NextDispensingDateMismatchError,
    PreparationMethod,
    QuantityAdjustmentInvalidError,
    SubstitutionCategory,
    SubstitutionDetail,
    SubstitutionWithoutChangeError,
    VerificationNotPassedError,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.medicine import (
    DispensingQuantity,
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineName,
    RpNumber,
)
from app.domain.staff.primitives import StaffId
from tests.factories.dispensing_factory import (
    DISPENSED_ON,
    GENERIC_CODE,
    GENERIC_NAME,
    create_dispensed_medicine,
    create_dispensed_rp,
    create_dispensing,
    create_identifier,
    create_quantity_adjustment,
    create_substitution,
    verify_passed,
)

_NEXT_DATE = NextDispensingDate(DISPENSED_ON.replace(day=25))
_CANCEL_REASON = DispensingCancellationReason("患者都合により交付前に中止した。")


class Test構造の不変条件:
    """集約単独で判定できるもの。"""

    def test_剤が1件も無いと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DispensedRpRequiredError):
            create_dispensing(dispensed_rps=())

    def test_薬品が1件も無い剤は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DispensedMedicineRequiredError):
            create_dispensed_rp(medicines=())

    def test_RP番号が重複すると_構築できない(self) -> None:
        """処方箋の剤との対応キーなので、重複すると突合が壊れる。"""
        # Arrange / Act / Assert
        with pytest.raises(DuplicatedDispensedRpNumberError):
            create_dispensing(
                dispensed_rps=(
                    create_dispensed_rp(rp_number=1),
                    create_dispensed_rp(rp_number=1),
                )
            )

    def test_RP番号が連続していなくても_構築できる(self) -> None:
        """分割調剤では処方箋の一部の剤だけを調剤しうるので欠番は正当。"""
        # Arrange / Act
        actual = create_dispensing(
            dispensed_rps=(
                create_dispensed_rp(rp_number=1),
                create_dispensed_rp(rp_number=3),
            )
        )

        # Assert
        assert actual.dispensed_rp_numbers == (RpNumber(1), RpNumber(3))

    def test_薬品連番が重複すると_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DuplicatedDispensedLineNumberError):
            create_dispensed_rp(
                medicines=(
                    create_dispensed_medicine(line_number=1),
                    create_dispensed_medicine(line_number=1, code="1111111111"),
                )
            )

    def test_指定したRP番号の剤を取り出せる(self) -> None:
        # Arrange
        process = create_dispensing(
            dispensed_rps=(
                create_dispensed_rp(rp_number=1),
                create_dispensed_rp(rp_number=2),
            )
        )

        # Act
        actual = process.find_rp(RpNumber(2))

        # Assert
        assert actual is not None
        assert actual.rp_number == RpNumber(2)
        assert process.find_rp(RpNumber(9)) is None


class Test分割理由と調剤回数:
    """リフィルの総使用回数は処方箋集約が持つのでここでは見ない。"""

    def test_後発医薬品の試用で3回目は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DispensingIterationOutOfRangeError, match="後発医薬品"):
            create_dispensing(
                iteration=3, split_reason=DispensingSplitReason.GENERIC_TRIAL
            )

    def test_医師の分割指示で4回目は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DispensingIterationOutOfRangeError):
            create_dispensing(
                iteration=4, split_reason=DispensingSplitReason.PRESCRIBER_INSTRUCTED
            )

    def test_長期保存の困難性等は_回数が大きくても構築できる(self) -> None:
        """注9 に回数上限の定めが無い。"""
        # Arrange / Act
        actual = create_dispensing(
            iteration=8, split_reason=DispensingSplitReason.LONG_TERM_STORAGE
        )

        # Assert
        assert actual.iteration.value == 8

    def test_長期保存の困難性等で1回目は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DispensingIterationOutOfRangeError):
            create_dispensing(
                iteration=1, split_reason=DispensingSplitReason.LONG_TERM_STORAGE
            )

    def test_分割理由が無ければ_回数の上限を課さない(self) -> None:
        """リフィルの上限は処方箋側の総使用回数であり Domain Service が見る。"""
        # Arrange / Act
        actual = create_dispensing(iteration=3)

        # Assert
        assert actual.split_reason is None


class Test調剤終了区分と次回調剤予定日:
    """電子処方箋調剤編のリフィル処方箋情報レコード(521)を検証する。"""

    def test_継続なのに次回予定日が無いと_構築できない(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing())

        # Act / Assert
        with pytest.raises(NextDispensingDateMismatchError):
            process.complete(completion_type=DispensingCompletionType.CONTINUES)

    def test_終了なのに次回予定日があると_構築できない(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing())

        # Act / Assert
        with pytest.raises(NextDispensingDateMismatchError):
            process.complete(
                completion_type=DispensingCompletionType.COMPLETED,
                next_dispensing_date=_NEXT_DATE,
            )

    def test_継続なら_次回予定日を記録して完了できる(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing())

        # Act
        actual = process.complete(
            completion_type=DispensingCompletionType.CONTINUES,
            next_dispensing_date=_NEXT_DATE,
        )

        # Assert
        assert actual.continues
        assert actual.next_dispensing_date == _NEXT_DATE
        assert actual.status is DispensingProcessStatus.COMPLETED

    def test_総使用回数に達していなくても_終了にできる(self) -> None:
        """規格は「達していないが次回以降の調剤が不要となった場合」も終了と定める。

        「``iteration == total_refill_count`` なら終了」という実装に倒すと、
        この正当なケースを表現できなくなる。
        """
        # Arrange
        process = verify_passed(create_dispensing(iteration=1))

        # Act
        actual = process.complete(completion_type=DispensingCompletionType.COMPLETED)

        # Assert
        assert not actual.continues
        assert actual.next_dispensing_date is None


class Test変更調剤:
    """3軸が独立していること。"""

    def test_代替調剤の変更前と変更後が同じだと_構築できない(self) -> None:
        """代替したことにして中身が同じ記録は、後発品実績を静かに壊す。"""
        # Arrange / Act / Assert
        with pytest.raises(SubstitutionWithoutChangeError):
            create_dispensed_medicine(substitution=create_substitution())

    def test_後発品へ変更すると_代替調剤として記録される(self) -> None:
        # Arrange / Act
        actual = create_dispensed_medicine(
            code=GENERIC_CODE,
            name=GENERIC_NAME,
            substitution=create_substitution(),
        )

        # Assert
        assert actual.is_substituted
        assert actual.substitution is not None
        assert actual.substitution.is_generic_substitution

    def test_名称だけ変わる代替も_記録できる(self) -> None:
        """コードなしの紙処方箋では、識別子が同じで名称だけ変わる代替がありうる。"""
        # Arrange
        substitution = SubstitutionDetail(
            category=SubstitutionCategory.DOSAGE_FORM_CHANGE,
            original_identifier=MedicineIdentifier(code_type=MedicineCodeType.NONE),
            original_name=MedicineName("処方箋記載の名称"),
        )

        # Act
        actual = create_dispensed_medicine(substitution=substitution)

        # Assert
        assert actual.is_substituted

    def test_同じ調製方法を重複指定すると_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DuplicatedPreparationMethodError):
            create_dispensed_medicine(
                preparations=(
                    PreparationMethod.UNIT_DOSE_PACKAGED,
                    PreparationMethod.UNIT_DOSE_PACKAGED,
                )
            )

    def test_一包化と自家製剤は_同時に記録できる(self) -> None:
        """加算の排他は Claim の責務。ここで排他にすると実施した事実を残せない。"""
        # Arrange / Act
        actual = create_dispensed_medicine(
            preparations=(
                PreparationMethod.UNIT_DOSE_PACKAGED,
                PreparationMethod.COMPOUNDED,
            )
        )

        # Assert
        assert len(actual.preparations) == 2

    def test_3軸は_同一薬品に同時に成立する(self) -> None:
        """後発品へ変更し、残薬分を減らし、一包化する、は同時に起こる。"""
        # Arrange / Act
        rp = create_dispensed_rp(
            quantity=14,
            quantity_adjustment=create_quantity_adjustment(prescribed_quantity=28),
            medicines=(
                create_dispensed_medicine(
                    code=GENERIC_CODE,
                    name=GENERIC_NAME,
                    substitution=create_substitution(),
                    preparations=(PreparationMethod.UNIT_DOSE_PACKAGED,),
                ),
            ),
        )

        # Assert
        assert rp.is_quantity_adjusted
        assert rp.has_substitution
        assert rp.medicines[0].preparations == (PreparationMethod.UNIT_DOSE_PACKAGED,)


class Test減数調剤:
    """用法・用量は変えず数量だけを減らす。"""

    def test_処方時と同じ数量では_減数調剤として構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(QuantityAdjustmentInvalidError):
            create_dispensed_rp(
                quantity=28,
                quantity_adjustment=create_quantity_adjustment(prescribed_quantity=28),
            )

    def test_処方時より多い数量では_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(QuantityAdjustmentInvalidError):
            create_dispensed_rp(
                quantity=30,
                quantity_adjustment=create_quantity_adjustment(prescribed_quantity=28),
            )

    def test_数量を0にはできない(self) -> None:
        """0にするなら処方箋の事前照会・削除が必要で、減数調剤ではない。"""
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError):
            create_dispensed_rp(quantity=0)

    def test_処方時の数量を保持するので_減数したことを検証できる(self) -> None:
        # Arrange / Act
        actual = create_dispensed_rp(
            quantity=14,
            quantity_adjustment=create_quantity_adjustment(prescribed_quantity=28),
        )

        # Assert
        assert actual.quantity_adjustment is not None
        assert actual.quantity_adjustment.prescribed_quantity == DispensingQuantity(28)
        assert actual.quantity == DispensingQuantity(14)


class Test鑑査:
    """処方鑑査（前）と最終鑑査（後）は別物。"""

    def test_処方鑑査を記録しても_状態は動かない(self) -> None:
        # Arrange
        process = create_dispensing()

        # Act
        actual = process.record_audit(
            auditor_id=StaffId.generate(),
            audited_at=AuditTimestamp(datetime(2026, 8, 24, 1, 0, tzinfo=UTC)),
            has_issues=False,
        )

        # Assert
        assert actual.audit is not None
        assert actual.status is DispensingProcessStatus.IN_PROGRESS

    def test_最終鑑査に合格すると_鑑査済へ進む(self) -> None:
        # Arrange
        process = create_dispensing()

        # Act
        actual = verify_passed(process)

        # Assert
        assert actual.status is DispensingProcessStatus.VERIFIED
        assert actual.is_verified

    def test_最終鑑査に不合格なら_調製中のまま留まる(self) -> None:
        """再調製できるようにする。状態を進めると「不合格なのに交付できる」。"""
        # Arrange
        process = create_dispensing()

        # Act
        actual = process.verify(
            verifier_id=StaffId.generate(),
            verified_at=VerificationTimestamp(datetime(2026, 8, 24, 2, 0, tzinfo=UTC)),
            result=VerificationResult.FAILED,
        )

        # Assert
        assert actual.status is DispensingProcessStatus.IN_PROGRESS
        assert not actual.is_verified

    def test_不合格後に再調製して_合格させられる(self) -> None:
        # Arrange
        process = create_dispensing().verify(
            verifier_id=StaffId.generate(),
            verified_at=VerificationTimestamp(datetime(2026, 8, 24, 2, 0, tzinfo=UTC)),
            result=VerificationResult.FAILED,
        )

        # Act
        actual = verify_passed(
            process.update_dispensed_rps(
                (
                    create_dispensed_rp(
                        medicines=(
                            create_dispensed_medicine(
                                code=GENERIC_CODE, name=GENERIC_NAME
                            ),
                        )
                    ),
                )
            )
        )

        # Assert
        assert actual.status is DispensingProcessStatus.VERIFIED
        assert actual.dispensed_rps[0].medicines[0].identifier == create_identifier(
            GENERIC_CODE
        )

    def test_調剤者本人が最終鑑査しても_合格させられる(self) -> None:
        """薬剤師が1人しかいない体制でも調剤を終えられる必要がある。

        夜間・休日当番や小規模店舗では、1人の薬剤師が調剤から最終鑑査までを
        担うことが薬剤師法上も適法に起こりうる。調剤者と鑑査者の分離は法人ごとの
        運用方針であって集約が単独で判定できる不変条件ではないため、ここでは
        同一人物を拒否しない。
        """
        # Arrange
        dispenser_id = StaffId.generate()
        process = create_dispensing(dispenser_id=dispenser_id)

        # Act
        actual = verify_passed(process, verifier_id=dispenser_id)

        # Assert
        assert actual.status is DispensingProcessStatus.VERIFIED
        assert actual.verification is not None
        assert actual.verification.verifier_id == dispenser_id


class Test状態遷移:
    """終端からは動かせない。"""

    def test_鑑査に合格していないと_完了できない(self) -> None:
        # Arrange
        process = create_dispensing()

        # Act / Assert
        with pytest.raises(VerificationNotPassedError):
            process.complete(completion_type=DispensingCompletionType.COMPLETED)

    def test_調製中から_中止できる(self) -> None:
        # Arrange
        process = create_dispensing()

        # Act
        actual = process.cancel(_CANCEL_REASON)

        # Assert
        assert actual.status is DispensingProcessStatus.CANCELLED
        assert actual.cancellation_reason == _CANCEL_REASON

    def test_鑑査済からも_交付前なら中止できる(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing())

        # Act
        actual = process.cancel(_CANCEL_REASON)

        # Assert
        assert actual.status is DispensingProcessStatus.CANCELLED

    def test_交付済からは_中止できない(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing()).complete(
            completion_type=DispensingCompletionType.COMPLETED
        )

        # Act / Assert
        with pytest.raises(DispensingStatusTransitionError):
            process.cancel(_CANCEL_REASON)

    def test_中止済みでは_調剤内容を変更できない(self) -> None:
        # Arrange
        process = create_dispensing().cancel(_CANCEL_REASON)

        # Act / Assert
        with pytest.raises(DispensingStatusTransitionError):
            process.update_dispensed_rps((create_dispensed_rp(),))

    def test_鑑査済では_処方鑑査を記録できない(self) -> None:
        # Arrange
        process = verify_passed(create_dispensing())

        # Act / Assert
        with pytest.raises(DispensingStatusTransitionError):
            process.record_audit(
                auditor_id=StaffId.generate(),
                audited_at=AuditTimestamp(datetime(2026, 8, 24, 3, 0, tzinfo=UTC)),
                has_issues=False,
            )

    def test_中止理由なしで中止状態は_構築できない(self) -> None:
        """理由の無い中止は調剤録の記載として再現できない。"""
        # Arrange
        process = create_dispensing()

        # Act / Assert
        with pytest.raises(CancellationReasonMismatchError):
            process.__class__(
                id=process.id,
                corporate_id=process.corporate_id,
                store_id=process.store_id,
                patient_id=process.patient_id,
                prescription_id=process.prescription_id,
                iteration=process.iteration,
                dispensed_date=process.dispensed_date,
                dispenser_id=process.dispenser_id,
                started_at=process.started_at,
                dispensed_rps=process.dispensed_rps,
                status=DispensingProcessStatus.CANCELLED,
            )


class Test導出プロパティ:
    """状態を持たずに導出できるもの。"""

    def test_1回目かどうかを判定できる(self) -> None:
        # Arrange / Act / Assert
        assert create_dispensing(iteration=1).is_first_iteration
        assert not create_dispensing(iteration=2).is_first_iteration

    def test_代替調剤した薬品だけを取り出せる(self) -> None:
        """変更制限との照合に使う。"""
        # Arrange
        process = create_dispensing(
            dispensed_rps=(
                create_dispensed_rp(
                    medicines=(
                        create_dispensed_medicine(line_number=1),
                        create_dispensed_medicine(
                            line_number=2,
                            code=GENERIC_CODE,
                            name=GENERIC_NAME,
                            substitution=create_substitution(),
                        ),
                    )
                ),
            )
        )

        # Act
        actual = process.substituted_medicines

        # Assert
        assert len(actual) == 1
        assert actual[0].name == MedicineName(GENERIC_NAME)

    def test_調剤薬品コードは_処方箋のコードと別に保持される(self) -> None:
        """代替調剤では実際に出した薬品が調剤結果として記録される。"""
        # Arrange
        medicine = create_dispensed_medicine(
            code=GENERIC_CODE, name=GENERIC_NAME, substitution=create_substitution()
        )

        # Act / Assert
        assert medicine.identifier.code == MedicineCode(GENERIC_CODE)
        assert medicine.substitution is not None
        assert medicine.substitution.original_identifier.code is not None
        assert medicine.substitution.original_identifier.code.value != GENERIC_CODE
