"""調剤のドメインサービスのテスト。

調剤回数、使用期間、次回予定日、変更制限、剤の対応など、
**Domain Service** が担う集約間の整合性を固定する。

いずれも処方箋集約または前回セッションを参照するため、集約の ``validate()`` では
判定できない。**本物の集約を引数で受け取る**形をここで固定する。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import cast

import pytest

from app.domain.dispensing import (
    DispensedMedicineNotInPrescriptionError,
    DispensedRpNotInPrescriptionError,
    DispensingCompletionType,
    DispensingOutsidePrescriptionPeriodError,
    DispensingScheduleOutOfRangeError,
    DispensingSplitReason,
    IterationExceedsInstructionError,
    NextDispensingDate,
    PreviousDispensingCompletedError,
    PreviousDispensingUnknownError,
    SplitInstructionMissingError,
    SubstitutionCategory,
    SubstitutionNotAllowedError,
)
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.services import (
    REFILL_SCHEDULE_TOLERANCE_DAYS,
    DispensingConsistencyService,
    verify_substitution_restriction_table,
)
from app.domain.prescription import (
    GenericSubstitutionRestrictionType,
    Prescription,
    PrescriptionManagementInfo,
    RefillCount,
    RefillInstruction,
    SplitCount,
    SplitInstruction,
    SplitIteration,
)
from tests.factories.dispensing_factory import (
    DISPENSED_ON,
    GENERIC_CODE,
    GENERIC_NAME,
    create_dispensed_medicine,
    create_dispensed_rp,
    create_dispensing,
    create_substitution,
    verify_passed,
)
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_rp,
)

_SERVICE = DispensingConsistencyService()
_NEXT_DATE = date(2026, 9, 21)


def _prescription(
    *,
    restriction: GenericSubstitutionRestrictionType | None = None,
    management_info: PrescriptionManagementInfo | None = None,
) -> Prescription:
    """調剤ファクトリの既定薬品に対応する処方箋を組み立てる。"""
    return create_prescription(
        rps=(create_rp(medicines=(create_medicine(restriction=restriction),)),),
        management_info=management_info,
    )


def _substituted_dispensing(
    category: SubstitutionCategory = SubstitutionCategory.GENERIC_SUBSTITUTION,
) -> DispensingProcess:
    """代替調剤を1件含む調剤セッションを組み立てる。"""
    return create_dispensing(
        dispensed_rps=(
            create_dispensed_rp(
                medicines=(
                    create_dispensed_medicine(
                        code=GENERIC_CODE,
                        name=GENERIC_NAME,
                        substitution=create_substitution(category=category),
                    ),
                )
            ),
        )
    )


def _continuing_previous(*, next_dispensing_on: date = _NEXT_DATE) -> DispensingProcess:
    """次回調剤予定日を記録して完了した前回セッションを組み立てる。"""
    return verify_passed(create_dispensing()).complete(
        completion_type=DispensingCompletionType.CONTINUES,
        next_dispensing_date=NextDispensingDate(next_dispensing_on),
    )


class Test剤と薬品の対応:
    """調剤した剤と処方箋の剤が対応することを検証する。"""

    def test_処方箋に無いRP番号を調剤すると_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(dispensed_rps=(create_dispensed_rp(rp_number=2),))

        # Act / Assert
        with pytest.raises(DispensedRpNotInPrescriptionError):
            _SERVICE.ensure_rps_match_prescription(process, _prescription())

    def test_処方箋に無い薬品連番を調剤すると_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(
            dispensed_rps=(
                create_dispensed_rp(
                    medicines=(create_dispensed_medicine(line_number=2),)
                ),
            )
        )

        # Act / Assert
        with pytest.raises(DispensedMedicineNotInPrescriptionError):
            _SERVICE.ensure_rps_match_prescription(process, _prescription())

    def test_処方箋の一部だけ調剤しても_通る(self) -> None:
        """分割調剤・減数調剤では処方箋の一部だけを調剤しうる。

        「全部調剤したこと」を要求する実装に倒すと、分割調剤が成立しなくなる。
        """
        # Arrange
        prescription = create_prescription(
            rps=(
                create_rp(rp_number=1, medicines=(create_medicine(),)),
                create_rp(
                    rp_number=2,
                    medicines=(create_medicine(code="1111111111", name="薬A"),),
                ),
            )
        )
        process = create_dispensing(dispensed_rps=(create_dispensed_rp(rp_number=1),))

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_rps_match_prescription(process, prescription)


class Test変更制限:
    """薬剤師法第23条第2項（処方医の同意なき変更の禁止）を検証する。"""

    def test_後発品変更不可なのに後発品へ変更すると_拒否される(self) -> None:
        # Arrange
        process = _substituted_dispensing()
        prescription = _prescription(
            restriction=GenericSubstitutionRestrictionType.NO_GENERIC
        )

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError, match="後発品変更不可"):
            _SERVICE.ensure_substitutions_are_allowed(process, prescription)

    def test_先発医薬品患者希望でも_後発品への変更は拒否される(self) -> None:
        """選定療養の患者希望も、後発品へ替えると希望に反する。"""
        # Arrange
        process = _substituted_dispensing()
        prescription = _prescription(
            restriction=GenericSubstitutionRestrictionType.BRAND_REQUESTED_BY_PATIENT
        )

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError):
            _SERVICE.ensure_substitutions_are_allowed(process, prescription)

    def test_後発品変更不可でも_剤形変更は禁じられない(self) -> None:
        """制限の種類ごとに禁じる代替が違う。一括で禁じる実装に倒さない。"""
        # Arrange
        process = _substituted_dispensing(SubstitutionCategory.DOSAGE_FORM_CHANGE)
        prescription = _prescription(
            restriction=GenericSubstitutionRestrictionType.NO_GENERIC
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_substitutions_are_allowed(process, prescription)

    @pytest.mark.parametrize(
        "category",
        [
            SubstitutionCategory.DOSAGE_FORM_CHANGE,
            SubstitutionCategory.STRENGTH_CHANGE,
        ],
    )
    def test_剤形変更不可及び含量規格変更不可は_両方を拒否する(
        self, category: SubstitutionCategory
    ) -> None:
        # Arrange
        process = _substituted_dispensing(category)
        restriction = GenericSubstitutionRestrictionType.NO_FORM_OR_STRENGTH_CHANGE
        prescription = _prescription(restriction=restriction)

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError):
            _SERVICE.ensure_substitutions_are_allowed(process, prescription)

    def test_変更制限が無ければ_何も課さない(self) -> None:
        # Arrange
        process = _substituted_dispensing()

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_substitutions_are_allowed(process, _prescription())

    def test_代替調剤していなければ_変更制限があっても通る(self) -> None:
        # Arrange
        process = create_dispensing()
        prescription = _prescription(
            restriction=GenericSubstitutionRestrictionType.NO_GENERIC
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_substitutions_are_allowed(process, prescription)

    def test_全ての変更制限が_対応表に定義されている(self) -> None:
        """読み込み時チェックが空振りしていないことを、利用側からも確かめる。"""
        # Arrange / Act / Assert: 例外を送出しないこと自体が表明
        verify_substitution_restriction_table(
            restriction_types=set(GenericSubstitutionRestrictionType),
            categories=set(SubstitutionCategory),
        )

    def test_対応表に無い変更制限があると_読み込み時に落ちる(self) -> None:
        """制限を足して対応表を更新し忘れる事故を、この向きで固定する。

        本物の列挙に値を足すことはできないので、検証関数へ「表に無い値」を
        渡して、検出ロジック自体が働くことを見る。
        """
        # Arrange
        unknown = cast(GenericSubstitutionRestrictionType, "unknown_restriction")

        # Act / Assert
        with pytest.raises(RuntimeError, match="定義漏れ"):
            verify_substitution_restriction_table(
                restriction_types={*GenericSubstitutionRestrictionType, unknown},
                categories=set(SubstitutionCategory),
            )


class Test調剤回数と処方箋の指示:
    """分割理由ごとの上限は集約が見るので、ここでは処方箋側だけ検証する。"""

    def test_通常処方箋で2回目は_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(iteration=2)

        # Act / Assert
        with pytest.raises(IterationExceedsInstructionError, match="通常処方箋"):
            _SERVICE.ensure_iteration_is_within_instruction(process, _prescription())

    def test_リフィル3回の処方箋なら_3回目まで通る(self) -> None:
        # Arrange
        prescription = _prescription(
            management_info=PrescriptionManagementInfo(
                refill=RefillInstruction(total_refill_count=RefillCount(3))
            )
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_iteration_is_within_instruction(
            create_dispensing(iteration=3), prescription
        )

    def test_リフィル総使用回数を超えると_拒否される(self) -> None:
        # Arrange
        prescription = _prescription(
            management_info=PrescriptionManagementInfo(
                refill=RefillInstruction(total_refill_count=RefillCount(3))
            )
        )

        # Act / Assert
        with pytest.raises(IterationExceedsInstructionError, match="リフィル"):
            _SERVICE.ensure_iteration_is_within_instruction(
                create_dispensing(iteration=4), prescription
            )

    def test_医師の分割指示なのに処方箋に指示が無いと_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(
            iteration=2, split_reason=DispensingSplitReason.PRESCRIBER_INSTRUCTED
        )

        # Act / Assert
        with pytest.raises(SplitInstructionMissingError):
            _SERVICE.ensure_iteration_is_within_instruction(process, _prescription())

    def test_処方箋の分割回数を超えると_拒否される(self) -> None:
        """集約は注11の上限3回までしか見ない。処方箋が2分割なら3回目は不正。"""
        # Arrange
        prescription = _prescription(
            management_info=PrescriptionManagementInfo(
                split=SplitInstruction(
                    total_split_count=SplitCount(2),
                    split_iteration=SplitIteration(1),
                )
            )
        )
        process = create_dispensing(
            iteration=3, split_reason=DispensingSplitReason.PRESCRIBER_INSTRUCTED
        )

        # Act / Assert
        with pytest.raises(IterationExceedsInstructionError, match="医師の分割指示"):
            _SERVICE.ensure_iteration_is_within_instruction(process, prescription)

    def test_薬局判断の分割調剤は_処方箋に指示が無くても通る(self) -> None:
        """注9・注10 は薬局の判断であり、処方箋には現れない。"""
        # Arrange
        process = create_dispensing(
            iteration=2, split_reason=DispensingSplitReason.LONG_TERM_STORAGE
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_iteration_is_within_instruction(process, _prescription())


class Test1回目の調剤日:
    """処方箋の使用期間は1回目の調剤にだけ課す。"""

    def test_使用期間内なら_通る(self) -> None:
        # Arrange / Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_schedule_is_valid(create_dispensing(), _prescription())

    def test_使用期限当日は_通る(self) -> None:
        """使用期限は当日を含む。"""
        # Arrange
        process = create_dispensing(dispensed_on=date(2026, 8, 27))

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_schedule_is_valid(process, _prescription())

    def test_使用期限の翌日は_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(dispensed_on=date(2026, 8, 28))

        # Act / Assert
        with pytest.raises(DispensingOutsidePrescriptionPeriodError):
            _SERVICE.ensure_schedule_is_valid(process, _prescription())

    def test_交付日より前は_拒否される(self) -> None:
        # Arrange
        process = create_dispensing(dispensed_on=date(2026, 8, 23))

        # Act / Assert
        with pytest.raises(DispensingOutsidePrescriptionPeriodError):
            _SERVICE.ensure_schedule_is_valid(process, _prescription())


class Test2回目以降の調剤日:
    """基準は前回セッションが記録した次回調剤予定日。"""

    @staticmethod
    def _second(dispensed_on: date) -> DispensingProcess:
        """2回目の調剤セッションを組み立てる。"""
        return create_dispensing(iteration=2, dispensed_on=dispensed_on)

    @pytest.mark.parametrize("offset", [-REFILL_SCHEDULE_TOLERANCE_DAYS, 0, 7])
    def test_前後7日以内なら_通る(self, offset: int) -> None:
        """境界値（±7日ちょうど）を含めて許容する。"""
        # Arrange
        process = self._second(_NEXT_DATE + timedelta(days=offset))

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_schedule_is_valid(
            process, _prescription(), previous=_continuing_previous()
        )

    @pytest.mark.parametrize("offset", [-8, 8])
    def test_前後7日を超えると_拒否される(self, offset: int) -> None:
        # Arrange
        process = self._second(_NEXT_DATE + timedelta(days=offset))

        # Act / Assert
        with pytest.raises(DispensingScheduleOutOfRangeError):
            _SERVICE.ensure_schedule_is_valid(
                process, _prescription(), previous=_continuing_previous()
            )

    def test_使用期限を過ぎていても_2回目以降は使用期間を課さない(self) -> None:
        """1回目だけが使用期間の対象。2回目以降は次回予定日で判定する。"""
        # Arrange
        process = self._second(_NEXT_DATE)

        # Act / Assert: 使用期限（2026-08-27）を大きく過ぎていても通る
        _SERVICE.ensure_schedule_is_valid(
            process, _prescription(), previous=_continuing_previous()
        )

    def test_前回セッションが渡されないと_通さずに拒否される(self) -> None:
        """他薬局実施分でも情報提供を通じて渡される前提。素通りさせない。"""
        # Arrange
        process = self._second(_NEXT_DATE)

        # Act / Assert
        with pytest.raises(PreviousDispensingUnknownError):
            _SERVICE.ensure_schedule_is_valid(process, _prescription())

    def test_前回が調剤終了なら_次の回はできない(self) -> None:
        # Arrange
        previous = verify_passed(create_dispensing()).complete(
            completion_type=DispensingCompletionType.COMPLETED
        )
        process = self._second(_NEXT_DATE)

        # Act / Assert
        with pytest.raises(PreviousDispensingCompletedError):
            _SERVICE.ensure_schedule_is_valid(
                process, _prescription(), previous=previous
            )

    def test_基準は投薬期間ではなく_記録された次回予定日(self) -> None:
        """予定日を変えると許容される調剤日も動くことで、基準を固定する。"""
        # Arrange
        shifted = _NEXT_DATE + timedelta(days=30)
        previous = _continuing_previous(next_dispensing_on=shifted)

        # Act / Assert: 元の予定日ちょうどでは範囲外になる
        with pytest.raises(DispensingScheduleOutOfRangeError):
            _SERVICE.ensure_schedule_is_valid(
                self._second(_NEXT_DATE), _prescription(), previous=previous
            )
        _SERVICE.ensure_schedule_is_valid(
            self._second(shifted), _prescription(), previous=previous
        )


class Test入口からの一括検証:
    """``ensure_consistent()`` が個別の検証を1つも飛ばしていないこと。

    UseCase は入口だけを呼ぶ。どれか1つを呼び忘れた実装に変えると、
    このクラスのいずれかが落ちる。
    """

    def test_剤の対応違反を_入口が検出する(self) -> None:
        # Arrange
        process = create_dispensing(dispensed_rps=(create_dispensed_rp(rp_number=2),))

        # Act / Assert
        with pytest.raises(DispensedRpNotInPrescriptionError):
            _SERVICE.ensure_consistent(process, _prescription())

    def test_変更制限違反を_入口が検出する(self) -> None:
        # Arrange
        prescription = _prescription(
            restriction=GenericSubstitutionRestrictionType.NO_GENERIC
        )

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError):
            _SERVICE.ensure_consistent(_substituted_dispensing(), prescription)

    def test_回数超過を_入口が検出する(self) -> None:
        # Arrange: リフィル総使用回数3回に対して4回目
        process = create_dispensing(iteration=4, dispensed_on=_NEXT_DATE)

        # Act / Assert
        with pytest.raises(IterationExceedsInstructionError):
            _SERVICE.ensure_consistent(
                process,
                _prescription(
                    management_info=PrescriptionManagementInfo(
                        refill=RefillInstruction(total_refill_count=RefillCount(3))
                    )
                ),
                previous=_continuing_previous(),
            )

    def test_調剤日違反を_入口が検出する(self) -> None:
        # Arrange
        process = create_dispensing(dispensed_on=date(2026, 8, 28))

        # Act / Assert
        with pytest.raises(DispensingOutsidePrescriptionPeriodError):
            _SERVICE.ensure_consistent(process, _prescription())

    def test_すべて満たしていれば_通る(self) -> None:
        # Arrange / Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_consistent(create_dispensing(), _prescription())

    def test_リフィル2回目も_すべて満たせば通る(self) -> None:
        # Arrange
        prescription = _prescription(
            management_info=PrescriptionManagementInfo(
                refill=RefillInstruction(total_refill_count=RefillCount(3))
            )
        )
        process = create_dispensing(iteration=2, dispensed_on=_NEXT_DATE)

        # Act / Assert: 例外を送出しないこと自体が表明
        _SERVICE.ensure_consistent(
            process, prescription, previous=_continuing_previous()
        )


def test_調剤日の既定値が_処方箋の使用期間内である() -> None:
    """ファクトリの既定値が期間外になると、他のテストが理由なく落ちる。"""
    # Arrange / Act
    prescription = _prescription()

    # Assert
    assert prescription.period.includes(DISPENSED_ON)
