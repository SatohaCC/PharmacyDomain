"""Claimドメインの不変条件テスト。"""

from __future__ import annotations

import pytest

from app.base.domain.exceptions import DomainValidationError
from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageBranchNumber,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    CoverageCombinationInvalidError,
    CoverageSnapshot,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)


def _create_insurance_snapshot() -> InsuranceCoverageSnapshot:
    """テスト用の医療保険スナップショットを生成する。"""
    return InsuranceCoverageSnapshot(
        insurer_number=ClaimInsurerNumber("01130012"),
        insured_symbol=ClaimCoverageSymbol("A"),
        insured_number=ClaimCoverageCode("456"),
        insured_type=ClaimCoverageInsuredType.SELF,
        benefit_ratio=ClaimCoverageBenefitRatio(70),
    )


def _create_public_snapshot(priority: int) -> PublicExpenseCoverageSnapshot:
    """テスト用の公費スナップショットを生成する。"""
    return PublicExpenseCoverageSnapshot(
        priority=ClaimCoveragePriority(priority),
        payer_number=ClaimPublicPayerNumber(f"1234567{priority}"),
        recipient_number=ClaimPublicRecipientNumber(f"123456{priority}"),
    )


@pytest.mark.parametrize("value", ["1", "0113001", "011300123", "0113001a"])
def test_請求側保険者番号_桁数か文字種が不正だと_ドメイン検証エラーになる(
    value: str,
) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        ClaimInsurerNumber(value)


@pytest.mark.parametrize("value", ["1", "123456789", "payer-1"])
def test_請求側公費負担者番号_8桁の数字以外だと_ドメイン検証エラーになる(
    value: str,
) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        ClaimPublicPayerNumber(value)


@pytest.mark.parametrize("value", ["1", "12345678", "recipient-1"])
def test_請求側公費受給者番号_7桁の数字以外だと_ドメイン検証エラーになる(
    value: str,
) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        ClaimPublicRecipientNumber(value)


@pytest.mark.parametrize("value", ["1", "123", "1a"])
def test_請求側枝番_2桁の数字以外だと_ドメイン検証エラーになる(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        ClaimCoverageBranchNumber(value)


def test_資格スナップショット_社保1件と公費2件を渡すと_順位順に保持される() -> None:
    # Arrange
    insurance = _create_insurance_snapshot()
    public_first = _create_public_snapshot(1)
    public_second = _create_public_snapshot(2)

    # Act
    actual = CoverageSnapshot(
        insurance=insurance,
        public_expenses=(public_second, public_first),
    )

    # Assert
    assert (actual.insurance, actual.public_expenses) == (
        insurance,
        (public_first, public_second),
    )


def test_資格スナップショット_空の組み合わせを渡すと_検証エラーになる() -> None:
    # Arrange / Act / Assert
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSnapshot()


def test_資格スナップショット_公費順位が重複すると_検証エラーになる() -> None:
    # Arrange
    public_first = _create_public_snapshot(1)
    another_public_first = PublicExpenseCoverageSnapshot(
        priority=ClaimCoveragePriority(1),
        payer_number=ClaimPublicPayerNumber("99999999"),
        recipient_number=ClaimPublicRecipientNumber("9999999"),
    )

    # Act / Assert
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSnapshot(public_expenses=(public_first, another_public_first))


@pytest.mark.parametrize("priorities", [(3,), (2,), (1, 3), (2, 3)])
def test_資格スナップショット_公費順位が第一公費から連続しないと_検証エラーになる(
    priorities: tuple[int, ...],
) -> None:
    # Arrange
    public_expenses = tuple(
        _create_public_snapshot(priority) for priority in priorities
    )

    # Act / Assert
    with pytest.raises(CoverageCombinationInvalidError):
        CoverageSnapshot(public_expenses=public_expenses)


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_資格スナップショット_公費順位が第一公費から連続していれば_生成できる(
    count: int,
) -> None:
    # Arrange
    public_expenses = tuple(
        _create_public_snapshot(priority) for priority in range(1, count + 1)
    )

    # Act
    actual = CoverageSnapshot(public_expenses=public_expenses)

    # Assert
    assert [item.priority.value for item in actual.public_expenses] == list(
        range(1, count + 1)
    )


def test_医療保険スナップショット_給付割合を省略すると_生成できない() -> None:
    # Arrange / Act / Assert
    # 給付割合は患者負担額を決める値であり、凍結対象として必須である。
    with pytest.raises(TypeError):
        InsuranceCoverageSnapshot(  # type: ignore[call-arg]
            insurer_number=ClaimInsurerNumber("01130012"),
            insured_symbol=ClaimCoverageSymbol("A"),
            insured_number=ClaimCoverageCode("456"),
            insured_type=ClaimCoverageInsuredType.SELF,
        )
