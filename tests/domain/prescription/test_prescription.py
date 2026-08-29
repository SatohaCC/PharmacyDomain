"""処方箋集約の不変条件と状態遷移のテスト。

``Aggregate.validate()`` が単独で判定できるものだけをここで固定する。
Domain Service / Boundary が守るもの
（麻薬・リフィル適用除外・薬剤師資格）は、集約を跨ぐため対象外。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.prescription import (
    DosageSupplement,
    DosageSupplementText,
    DosageSupplementType,
    GenericSubstitutionRestriction,
    GenericSubstitutionRestrictionType,
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    InquiryNumber,
    InquiryResultType,
    MedicineCodeTypeNotAllowedError,
    MedicineLineNumberSequenceError,
    MedicineSupplement,
    MedicineSupplementText,
    MedicineSupplementType,
    OpenInquiryExistsError,
    PrescriptionMedicineRequiredError,
    PrescriptionRpRequiredError,
    PrescriptionSourceType,
    PrescriptionStatus,
    PrescriptionStatusTransitionError,
    RpNumberSequenceError,
    UnequalDosageInstruction,
    UnequalDosageTotalMismatchError,
)
from app.domain.prescription.primitives import verify_supplement_code_partition
from app.domain.shared.medicine import (
    DosageAmount,
    MedicineCodeType,
)
from app.domain.shared.public_expense import PublicExpenseBurden
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_response,
    create_rp,
    start_inquiry,
)


class Test構造の整合性:
    """RP・薬品明細の構造的な不変条件を検証する。"""

    def test_剤が1件もない処方箋は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(PrescriptionRpRequiredError):
            create_prescription(rps=())

    def test_薬品が1件もない剤は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(PrescriptionMedicineRequiredError):
            create_rp(medicines=())

    def test_RP番号が1から始まらないと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(RpNumberSequenceError):
            create_prescription(rps=(create_rp(rp_number=2),))

    def test_RP番号に欠番があると_構築できない(self) -> None:
        # Arrange
        rps = (create_rp(rp_number=1), create_rp(rp_number=3))

        # Act / Assert
        with pytest.raises(RpNumberSequenceError):
            create_prescription(rps=rps)

    def test_RP番号が重複すると_構築できない(self) -> None:
        # Arrange
        rps = (create_rp(rp_number=1), create_rp(rp_number=1))

        # Act / Assert
        with pytest.raises(RpNumberSequenceError):
            create_prescription(rps=rps)

    def test_RP番号が連続していれば_構築できる(self) -> None:
        # Arrange
        rps = (create_rp(rp_number=1), create_rp(rp_number=2))

        # Act
        actual = create_prescription(rps=rps)

        # Assert
        assert len(actual.rps) == 2

    def test_RP内連番に欠番があると_構築できない(self) -> None:
        # Arrange
        medicines = (create_medicine(line_number=1), create_medicine(line_number=3))

        # Act / Assert
        with pytest.raises(MedicineLineNumberSequenceError):
            create_rp(medicines=medicines)

    def test_RP内連番のエラーメッセージに_対象のRP番号が含まれる(self) -> None:
        # Arrange
        medicines = (create_medicine(line_number=2),)

        # Act / Assert
        with pytest.raises(MedicineLineNumberSequenceError, match="対象のRP番号: 5"):
            create_rp(rp_number=5, medicines=medicines)


class Test電子処方箋の薬品コード種別:
    """電子処方箋処方編の別表15を検証する。

    紙処方箋（JAHIS）では使えるコード種別が電子処方箋では使えない。
    受領元形式と組み合わせて初めて判定できるため、集約が持つ。
    """

    @pytest.mark.parametrize(
        "code_type",
        [MedicineCodeType.RECEIPT, MedicineCodeType.YJ, MedicineCodeType.GENERIC],
    )
    def test_電子処方箋で_許可された種別なら_構築できる(
        self, code_type: MedicineCodeType
    ) -> None:
        # Arrange
        rps = (create_rp(medicines=(create_medicine(code_type=code_type),)),)

        # Act
        actual = create_prescription(
            source_type=PrescriptionSourceType.ELECTRONIC, rps=rps
        )

        # Assert
        assert actual.source_type is PrescriptionSourceType.ELECTRONIC

    @pytest.mark.parametrize(
        ("code_type", "code"),
        [
            (MedicineCodeType.MHLW, "1234567890"),
            (MedicineCodeType.HOT, "123456789"),
        ],
    )
    def test_電子処方箋で_使用しない種別だと_構築できない(
        self, code_type: MedicineCodeType, code: str
    ) -> None:
        """別表15 で 3 と 6 は「使用しない」と定められている。"""
        # Arrange
        rps = (create_rp(medicines=(create_medicine(code_type=code_type, code=code),)),)

        # Act / Assert
        with pytest.raises(MedicineCodeTypeNotAllowedError):
            create_prescription(source_type=PrescriptionSourceType.ELECTRONIC, rps=rps)

    def test_電子処方箋で_コードなしだと_構築できない(self) -> None:
        """別表15 で 1 は「未使用」と定められている。"""
        # Arrange
        rps = (
            create_rp(
                medicines=(create_medicine(code_type=MedicineCodeType.NONE, code=None),)
            ),
        )

        # Act / Assert
        with pytest.raises(MedicineCodeTypeNotAllowedError):
            create_prescription(source_type=PrescriptionSourceType.ELECTRONIC, rps=rps)

    @pytest.mark.parametrize(
        ("code_type", "code"),
        [
            (MedicineCodeType.NONE, None),
            (MedicineCodeType.MHLW, "1234567890"),
            (MedicineCodeType.HOT, "123456789"),
        ],
    )
    def test_紙処方箋なら_同じ種別でも_構築できる(
        self, code_type: MedicineCodeType, code: str | None
    ) -> None:
        """JAHIS では 1・3・6 のいずれも使用できる。規格差を型で表現している。"""
        # Arrange
        rps = (create_rp(medicines=(create_medicine(code_type=code_type, code=code),)),)

        # Act
        actual = create_prescription(
            source_type=PrescriptionSourceType.PAPER_QR, rps=rps
        )

        # Assert
        assert actual.source_type is PrescriptionSourceType.PAPER_QR

    def test_エラーメッセージに_指定された種別名が含まれる(self) -> None:
        # Arrange
        rps = (
            create_rp(
                medicines=(
                    create_medicine(code_type=MedicineCodeType.HOT, code="123456789"),
                )
            ),
        )

        # Act / Assert
        with pytest.raises(MedicineCodeTypeNotAllowedError, match="HOTコード"):
            create_prescription(source_type=PrescriptionSourceType.ELECTRONIC, rps=rps)


class Test薬品補足と変更制限の振り分け:
    """処方編の別表16を2つの型へ振り分けた結果の整合性を検証する。"""

    def test_別表16のコードは_2つの型へ重複なく分割されている(self) -> None:
        """調製指示と変更制限にコードの重なりが無いことを確認する。

        重なりがあると、薬品補足を規格へ往復変換したときにどちらの型へ
        戻すかが決まらない。実行時に個別インスタンスを検査する必要は無く
        （型が分かれている以上インスタンス単位では衝突しえない）、
        危険なのは後から enum へ値を足すときなので import 時に検証している。
        """
        # Arrange
        supplement_codes = {member.record_code for member in MedicineSupplementType}
        restriction_codes = {
            member.record_code for member in GenericSubstitutionRestrictionType
        }

        # Act / Assert
        assert supplement_codes & restriction_codes == set()

    def test_別表16のコードは_2つの型で漏れなく覆われている(self) -> None:
        """規格が定める 1〜8 のすべてがどちらかの型に存在することを確認する。"""
        # Arrange
        supplement_codes = {member.record_code for member in MedicineSupplementType}
        restriction_codes = {
            member.record_code for member in GenericSubstitutionRestrictionType
        }

        # Act / Assert: 9〜99 は「（未使用）」なので対象外
        assert supplement_codes | restriction_codes == {
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
        }

    def test_分割が崩れると_モジュール読み込み時に落ちる(self) -> None:
        """検証関数そのものが機能することを、重複した集合で確かめる。"""
        # Arrange / Act / Assert
        with pytest.raises(RuntimeError, match="両方に定義されています"):
            verify_supplement_code_partition(
                supplement_codes={"1", "3"}, restriction_codes={"3", "4"}
            )

    def test_コードに漏れがあると_モジュール読み込み時に落ちる(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(RuntimeError, match="未定義"):
            verify_supplement_code_partition(
                supplement_codes={"1", "2"}, restriction_codes={"3"}
            )

    def test_同じ薬品補足区分を重複指定すると_構築できない(self) -> None:
        # Arrange
        supplement = MedicineSupplement(
            supplement_type=MedicineSupplementType.UNIT_DOSE,
            text=MedicineSupplementText("一包化"),
        )

        # Act / Assert
        with pytest.raises(Exception, match="複数指定できません"):
            create_medicine().__class__(
                line_number=create_medicine().line_number,
                identifier=create_medicine().identifier,
                name=create_medicine().name,
                amount=create_medicine().amount,
                unit=create_medicine().unit,
                supplements=(supplement, supplement),
            )

    def test_同じ用法補足区分を重複指定すると_構築できない(self) -> None:
        # Arrange
        supplement = DosageSupplement(
            supplement_type=DosageSupplementType.UNIT_DOSE,
            text=DosageSupplementText("一包化"),
        )
        rp = create_rp()

        # Act / Assert
        with pytest.raises(Exception, match="複数指定できません"):
            type(rp)(
                rp_number=rp.rp_number,
                category=rp.category,
                quantity=rp.quantity,
                dosage_instruction=rp.dosage_instruction,
                medicines=rp.medicines,
                dosage_supplements=(supplement, supplement),
            )

    def test_変更制限と調製指示のコードが異なれば_構築できる(self) -> None:
        # Arrange
        restriction = GenericSubstitutionRestriction(
            restriction_type=GenericSubstitutionRestrictionType.NO_GENERIC,
        )
        supplement = MedicineSupplement(
            supplement_type=MedicineSupplementType.UNIT_DOSE,
            text=MedicineSupplementText("一包化"),
        )
        base = create_medicine()

        # Act
        actual = type(base)(
            line_number=base.line_number,
            identifier=base.identifier,
            name=base.name,
            amount=base.amount,
            unit=base.unit,
            substitution_restriction=restriction,
            supplements=(supplement,),
        )

        # Assert: 後発品変更不可(3) と 一包化(1) は別コードなので併存できる
        assert actual.substitution_restriction is not None
        assert len(actual.supplements) == 1


class Test不均等服用:
    """各回服用量の合計が1日量と一致することを検証する。"""

    def test_合計が1日量と一致すれば_構築できる(self) -> None:
        # Arrange
        unequal = UnequalDosageInstruction(
            doses=(DosageAmount(Decimal("2")), DosageAmount(Decimal("1")))
        )
        base = create_medicine(amount="3")

        # Act
        actual = type(base)(
            line_number=base.line_number,
            identifier=base.identifier,
            name=base.name,
            amount=base.amount,
            unit=base.unit,
            unequal_dosage=unequal,
        )

        # Assert
        assert actual.unequal_dosage is not None

    def test_実在する0_05刻みでも_合計が一致すれば構築できる(self) -> None:
        """``float`` ならここが誤差で落ちる（0.05×3 が 0.15 にならない）。"""
        # Arrange
        unequal = UnequalDosageInstruction(
            doses=(
                DosageAmount(Decimal("0.05")),
                DosageAmount(Decimal("0.05")),
                DosageAmount(Decimal("0.05")),
            )
        )
        base = create_medicine(amount="0.15")

        # Act
        actual = type(base)(
            line_number=base.line_number,
            identifier=base.identifier,
            name=base.name,
            amount=base.amount,
            unit=base.unit,
            unequal_dosage=unequal,
        )

        # Assert
        assert actual.unequal_dosage is not None

    def test_合計が1日量と一致しないと_構築できない(self) -> None:
        # Arrange
        unequal = UnequalDosageInstruction(
            doses=(DosageAmount(Decimal("2")), DosageAmount(Decimal("2")))
        )
        base = create_medicine(amount="3")

        # Act / Assert
        with pytest.raises(UnequalDosageTotalMismatchError, match="合計: 4"):
            type(base)(
                line_number=base.line_number,
                identifier=base.identifier,
                name=base.name,
                amount=base.amount,
                unit=base.unit,
                unequal_dosage=unequal,
            )

    def test_1回分だけの不均等指示は_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(UnequalDosageTotalMismatchError, match="2回分以上"):
            UnequalDosageInstruction(doses=(DosageAmount(Decimal("1")),))


class Test疑義照会:
    """疑義照会の追加・回答と、状態を持たない導出を検証する。"""

    def test_疑義照会を開始すると_未回答として記録される(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act
        actual = start_inquiry(prescription)

        # Assert
        assert actual.has_open_inquiry
        assert actual.inquiries[0].is_open

    def test_疑義照会の連番は_1から採番される(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription())

        # Act
        actual = start_inquiry(prescription)

        # Assert
        assert [inquiry.id.value for inquiry in actual.inquiries] == [1, 2]

    def test_回答を記録すると_未回答ではなくなる(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription())

        # Act
        actual = prescription.resolve_inquiry(
            inquiry_number=InquiryNumber(1), response=create_response()
        )

        # Assert
        assert not actual.has_open_inquiry

    def test_回答済みの照会に_再度回答すると_拒否される(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription()).resolve_inquiry(
            inquiry_number=InquiryNumber(1), response=create_response()
        )

        # Act / Assert
        with pytest.raises(InquiryAlreadyResolvedError):
            prescription.resolve_inquiry(
                inquiry_number=InquiryNumber(1), response=create_response()
            )

    def test_存在しない連番へ回答すると_拒否される(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription())

        # Act / Assert
        with pytest.raises(InquiryNotFoundError, match="照会連番: 2"):
            prescription.resolve_inquiry(
                inquiry_number=InquiryNumber(2), response=create_response()
            )

    def test_処方削除の回答は_調剤不能として導出される(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription())

        # Act
        actual = prescription.resolve_inquiry(
            inquiry_number=InquiryNumber(1),
            response=create_response(result_type=InquiryResultType.DELETED),
        )

        # Assert
        assert actual.has_blocking_inquiry

    def test_複数の照会のうち1件でも未回答なら_未回答として導出される(self) -> None:
        # Arrange
        prescription = start_inquiry(start_inquiry(create_prescription()))

        # Act
        actual = prescription.resolve_inquiry(
            inquiry_number=InquiryNumber(1), response=create_response()
        )

        # Assert
        assert actual.has_open_inquiry


class Test状態遷移:
    """``INQUIRING`` を状態に持たない設計の帰結を固定する。"""

    def test_初期状態は_受付済(self) -> None:
        # Arrange / Act
        actual = create_prescription()

        # Assert
        assert actual.status is PrescriptionStatus.RECEIVED

    def test_未回答の照会があると_調剤可能にできない(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription())

        # Act / Assert
        with pytest.raises(OpenInquiryExistsError):
            prescription.ready_for_dispensing()

    def test_照会に回答すれば_調剤可能にできる(self) -> None:
        # Arrange
        prescription = start_inquiry(create_prescription()).resolve_inquiry(
            inquiry_number=InquiryNumber(1), response=create_response()
        )

        # Act
        actual = prescription.ready_for_dispensing()

        # Assert
        assert actual.status is PrescriptionStatus.READY_FOR_DISPENSING

    def test_照会が1件もなければ_そのまま調剤可能にできる(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act
        actual = prescription.ready_for_dispensing()

        # Assert
        assert actual.status is PrescriptionStatus.READY_FOR_DISPENSING

    def test_調剤可能から_受付済へ差し戻せる(self) -> None:
        # Arrange
        prescription = create_prescription().ready_for_dispensing()

        # Act
        actual = prescription.return_for_inquiry()

        # Assert: 状態を巻き戻すのではなく、明示的な差戻し操作として表す
        assert actual.status is PrescriptionStatus.RECEIVED

    def test_調剤可能から_調剤済へ遷移できる(self) -> None:
        # Arrange
        prescription = create_prescription().ready_for_dispensing()

        # Act
        actual = prescription.complete_dispensing()

        # Assert
        assert actual.status is PrescriptionStatus.DISPENSED
        assert actual.status.is_terminal

    def test_受付済から_いきなり調剤済にはできない(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError, match="調剤済"):
            prescription.complete_dispensing()

    def test_調剤済からは_取消できない(self) -> None:
        # Arrange
        prescription = (
            create_prescription().ready_for_dispensing().complete_dispensing()
        )

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError):
            prescription.cancel()

    def test_取消済からは_調剤可能にできない(self) -> None:
        # Arrange
        prescription = create_prescription().cancel()

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError):
            prescription.ready_for_dispensing()

    def test_終端状態では_疑義照会を追加できない(self) -> None:
        # Arrange
        prescription = create_prescription().cancel()

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError):
            start_inquiry(prescription)

    def test_状態変更は_新しいインスタンスを返す(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act
        changed = prescription.ready_for_dispensing()

        # Assert: 元のインスタンスは変わらない（frozen）
        assert prescription.status is PrescriptionStatus.RECEIVED
        assert changed is not prescription
        assert changed.id == prescription.id


class Test導出プロパティ:
    def test_薬品識別子は_全ての剤から集約される(self) -> None:
        # Arrange
        rps = (
            create_rp(rp_number=1, medicines=(create_medicine(line_number=1),)),
            create_rp(
                rp_number=2,
                medicines=(
                    create_medicine(line_number=1),
                    create_medicine(line_number=2),
                ),
            ),
        )

        # Act
        actual = create_prescription(rps=rps)

        # Assert
        assert len(actual.medicine_identifiers) == 3

    def test_公費負担区分は_薬品ごとに保持できる(self) -> None:
        # Arrange
        base = create_medicine()

        # Act
        actual = type(base)(
            line_number=base.line_number,
            identifier=base.identifier,
            name=base.name,
            amount=base.amount,
            unit=base.unit,
            public_expense_burden=PublicExpenseBurden(first=True),
        )

        # Assert
        assert actual.public_expense_burden is not None
        assert actual.public_expense_burden.bears_any
