"""Claimドメインの不変条件テスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

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
    CoverageUsageTimestamp,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.claim.coverage_usage import CoverageUsage
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.fakes.in_memory_coverage_usage_repository import (
    InMemoryCoverageUsageRepository,
)

_JST = timezone(timedelta(hours=9))


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


def test_適用資格利用日時_JSTを渡すと_UTCオフセットで保持される() -> None:
    # Arrange
    value = datetime(2026, 8, 17, 12, 30, tzinfo=_JST)

    # Act
    actual = CoverageUsageTimestamp(value)

    # Assert
    # aware datetime の `==` は瞬時で比較するためオフセットの違いを検出できない。
    # 正規化されたことを確かめるには保持している表現そのものを比較する。
    assert actual.value.isoformat() == "2026-08-17T03:30:00+00:00"


def test_適用資格利用日時_UTCを渡すと_表現が変わらない() -> None:
    # Arrange
    value = datetime(2026, 8, 17, 3, 30, tzinfo=UTC)

    # Act
    actual = CoverageUsageTimestamp(value)

    # Assert
    assert actual.value.isoformat() == "2026-08-17T03:30:00+00:00"


def test_適用資格利用日時_異なるタイムゾーンを渡すと_同一のUTC表現になる() -> None:
    # Arrange
    values = (
        datetime(2026, 8, 17, 3, 30, tzinfo=UTC),
        datetime(2026, 8, 17, 12, 30, tzinfo=_JST),
        datetime(2026, 8, 16, 22, 30, tzinfo=timezone(timedelta(hours=-5))),
    )

    # Act
    actual = tuple(CoverageUsageTimestamp(value).value.isoformat() for value in values)

    # Assert
    assert actual == ("2026-08-17T03:30:00+00:00",) * 3


def test_適用資格利用日時_naive日時を渡すと_ドメイン検証エラーになる() -> None:
    # Arrange
    value = datetime(2026, 8, 17, 3, 30)

    # Act / Assert
    with pytest.raises(DomainValidationError):
        CoverageUsageTimestamp(value)


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


def _create_usage(
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    patient_id: PatientId,
    applied_at: datetime,
) -> CoverageUsage:
    """テスト用の利用履歴を生成する。"""
    return CoverageUsage.create(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        applied_at=CoverageUsageTimestamp(applied_at),
        snapshot=CoverageSnapshot(public_expenses=(_create_public_snapshot(1),)),
    )


@pytest.mark.asyncio
async def test_資格利用履歴Repository_タイムゾーンが混在しても_最新履歴を返す() -> None:
    # Arrange
    repository = InMemoryCoverageUsageRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    older = _create_usage(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        applied_at=datetime(2026, 8, 17, 3, 0, tzinfo=UTC),
    )
    latest = _create_usage(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        applied_at=datetime(2026, 8, 17, 12, 30, tzinfo=_JST),
    )
    await repository.save(older)
    await repository.save(latest)

    # Act
    actual = await repository.get_latest(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
    )

    # Assert
    assert actual is not None and actual.id == latest.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("corporate_id", "store_id", "patient_id"),
    [
        ("other_corporate", "same_store", "same_patient"),
        ("same_corporate", "other_store", "same_patient"),
        ("same_corporate", "same_store", "other_patient"),
    ],
)
async def test_資格利用履歴Repository_法人店舗患者が異なると_履歴を返さない(
    corporate_id: str,
    store_id: str,
    patient_id: str,
) -> None:
    # Arrange
    repository = InMemoryCoverageUsageRepository()
    target_corporate_id = CorporateId.generate()
    target_store_id = StoreId.generate()
    target_patient_id = PatientId.generate()
    other_corporate_id = CorporateId.generate()
    other_store_id = StoreId.generate()
    other_patient_id = PatientId.generate()
    stored = _create_usage(
        corporate_id=(
            other_corporate_id
            if corporate_id == "other_corporate"
            else target_corporate_id
        ),
        store_id=other_store_id if store_id == "other_store" else target_store_id,
        patient_id=other_patient_id
        if patient_id == "other_patient"
        else target_patient_id,
        applied_at=datetime(2026, 8, 17, 3, tzinfo=UTC),
    )
    await repository.save(stored)

    # Act
    actual = await repository.get_latest(
        corporate_id=target_corporate_id,
        store_id=target_store_id,
        patient_id=target_patient_id,
    )

    # Assert
    assert actual is None
