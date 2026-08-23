"""Receptionの適用資格選択とその履歴集約の不変条件テスト。

以前は「元資格ID列」と「スナップショット」が別フィールドで、対応は並び順の
規約だった。枠構造にしたことで崩れた対応が**表現できなく**なったことを、
ここで固定する。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    CoverageCombinationInvalidError,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelection,
    CoverageSelectionInvalidError,
    CoverageSelectionRecord,
    OperatorPrincipalId,
    SelectedInsuranceSource,
    SelectedPublicExpenseSource,
    SourceCoverageId,
)
from app.domain.store.primitives import StoreId


def _insurance_frame(
    source_coverage_id: SourceCoverageId | None = None,
) -> SelectedInsuranceSource:
    """テスト用の医療保険枠を生成する。"""
    return SelectedInsuranceSource(
        source_coverage_id=source_coverage_id or SourceCoverageId.generate(),
        values=InsuranceCoverageSnapshot(
            insurer_number=ClaimInsurerNumber("01130012"),
            insured_symbol=ClaimCoverageSymbol("A"),
            insured_number=ClaimCoverageCode("456"),
            insured_type=ClaimCoverageInsuredType.SELF,
            benefit_ratio=ClaimCoverageBenefitRatio(70),
        ),
    )


def _public_frame(
    priority: int,
    source_coverage_id: SourceCoverageId | None = None,
) -> SelectedPublicExpenseSource:
    """テスト用の公費枠を生成する。"""
    return SelectedPublicExpenseSource(
        source_coverage_id=source_coverage_id or SourceCoverageId.generate(),
        values=PublicExpenseCoverageSnapshot(
            priority=ClaimCoveragePriority(priority),
            payer_number=ClaimPublicPayerNumber(f"1234567{priority}"),
            recipient_number=ClaimPublicRecipientNumber(f"123456{priority}"),
        ),
    )


def test_適用資格選択_公費を順位の逆順で渡すと_順位順に正規化される() -> None:
    # Arrange
    second, first = _public_frame(2), _public_frame(1)

    # Act
    actual = CoverageSelection(public_expenses=(second, first))

    # Assert: 並び順という自由度が消え、どの入力順でも同一の値になる
    assert actual.public_expenses == (first, second)
    assert actual == CoverageSelection(public_expenses=(first, second))


def test_適用資格選択_元IDは医療保険から公費順位順で導出される() -> None:
    # Arrange
    insurance = _insurance_frame()
    second, first = _public_frame(2), _public_frame(1)

    # Act
    actual = CoverageSelection(
        insurance=insurance, public_expenses=(second, first)
    ).source_coverage_ids

    # Assert: 崩れた並びを保持する記憶域が存在しない
    assert actual == (
        insurance.source_coverage_id,
        first.source_coverage_id,
        second.source_coverage_id,
    )


def test_適用資格選択_スナップショットは枠と同じ値と順序になる() -> None:
    # Arrange
    insurance = _insurance_frame()
    first, second = _public_frame(1), _public_frame(2)

    # Act
    actual = CoverageSelection(
        insurance=insurance, public_expenses=(second, first)
    ).snapshot

    # Assert
    assert actual.insurance == insurance.values
    assert actual.public_expenses == (first.values, second.values)


def test_適用資格選択_同じ元IDを医療保険枠と公費枠に指定すると_選択エラーになる() -> (
    None
):
    # Arrange
    shared = SourceCoverageId.generate()

    # Act / Assert
    with pytest.raises(CoverageSelectionInvalidError):
        CoverageSelection(
            insurance=_insurance_frame(shared),
            public_expenses=(_public_frame(1, shared),),
        )


def test_適用資格選択_枠が一つもないと_組み合わせ検証エラーになる() -> None:
    # Arrange / Act / Assert
    # 値側の規則なので Claim の例外を透過させる（Receptionで包み直すと二重定義になる）
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSelection()


def test_適用資格選択_公費順位が第一公費から連続しないと_組み合わせ検証エラーになる() -> (
    None
):
    # Arrange / Act / Assert
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSelection(public_expenses=(_public_frame(2),))


def test_適用資格選択_公費が第五以降を含むと_組み合わせ検証エラーになる() -> None:
    # Arrange / Act / Assert
    # ClaimCoveragePriority が 1..4 しか許さないため、5件目は必ず重複になる。
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSelection(
            public_expenses=(
                _public_frame(1),
                _public_frame(2),
                _public_frame(3),
                _public_frame(4),
                _public_frame(4),
            )
        )


def test_適用資格選択履歴_選択を渡すと_元IDとスナップショットが導出される() -> None:
    # Arrange
    insurance = _insurance_frame()
    first = _public_frame(1)
    selection = CoverageSelection(insurance=insurance, public_expenses=(first,))

    # Act
    actual = CoverageSelectionRecord.create(
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        patient_id=PatientId.generate(),
        applied_on=CoverageAppliedOn(date(2026, 8, 23)),
        selection=selection,
        recorded_at=CoverageRecordedAt(datetime(2026, 8, 23, 3, 0, tzinfo=UTC)),
        recorded_by=OperatorPrincipalId("operator-1"),
    )

    # Assert: 独立した記憶域を持たず、常に枠構造と一致する
    assert actual.source_coverage_ids == (
        insurance.source_coverage_id,
        first.source_coverage_id,
    )
    assert actual.snapshot == selection.snapshot
