"""最新履歴候補の取得と再検証のテスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.claim.exceptions import (
    ClaimPatientNotFoundError,
    ClaimStoreNotFoundError,
)
from app.application.claim.get_last_coverage_usage import (
    GetLastCoverageUsageQuery,
    GetLastCoverageUsageUseCase,
)
from app.domain.claim.coverage_snapshot import (
    CoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.claim.coverage_usage import CoverageUsage
from app.domain.claim.primitives import (
    ClaimCoveragePriority,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    CoverageUsageTimestamp,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.claim_reference_boundaries import (
    FakeCoverageValidity,
    FakePatientReference,
    FakeStoreReference,
)
from tests.fakes.in_memory_coverage_usage_repository import (
    InMemoryCoverageUsageRepository,
)

_APPLIED_ON = date(2026, 8, 17)


class _Fixture:
    """ユースケースと依存フェイクをまとめて保持するテスト用の器。"""

    def __init__(self, *, valid: bool) -> None:
        self.corporate_id = CorporateId.generate()
        self.store_id = StoreId.generate()
        self.patient_id = PatientId.generate()
        self.repository = InMemoryCoverageUsageRepository()
        self.store_reference = FakeStoreReference()
        self.patient_reference = FakePatientReference()
        self.coverage_validity = FakeCoverageValidity(valid=valid)
        self.use_case = GetLastCoverageUsageUseCase(
            self.repository,
            create_vendor_corporate_access(),
            self.store_reference,
            self.patient_reference,
            self.coverage_validity,
        )

    def register_references(self) -> None:
        """店舗と患者を存在させる。"""
        self.store_reference.register(
            corporate_id=self.corporate_id,
            store_id=self.store_id,
        )
        self.patient_reference.register(
            corporate_id=self.corporate_id,
            patient_id=self.patient_id,
        )

    def build_query(self) -> GetLastCoverageUsageQuery:
        """テスト対象のクエリを組み立てる。"""
        return GetLastCoverageUsageQuery(
            corporate_id=str(self.corporate_id.value),
            store_id=str(self.store_id.value),
            patient_id=str(self.patient_id.value),
            applied_on=_APPLIED_ON,
        )

    async def save_usage(self) -> CoverageUsage:
        """利用履歴を1件保存して返す。"""
        usage = CoverageUsage.create(
            corporate_id=self.corporate_id,
            store_id=self.store_id,
            patient_id=self.patient_id,
            applied_at=CoverageUsageTimestamp(datetime(2026, 7, 1, 3, tzinfo=UTC)),
            snapshot=CoverageSnapshot(
                public_expenses=(
                    PublicExpenseCoverageSnapshot(
                        priority=ClaimCoveragePriority(1),
                        payer_number=ClaimPublicPayerNumber("12345678"),
                        recipient_number=ClaimPublicRecipientNumber("1234567"),
                    ),
                )
            ),
        )
        await self.repository.save(usage)
        return usage


@pytest.mark.asyncio
async def test_最新履歴取得_履歴がなければ_Noneを返す() -> None:
    # Arrange
    fixture = _Fixture(valid=True)
    fixture.register_references()

    # Act
    actual = await fixture.use_case.execute(fixture.build_query())

    # Assert
    assert actual is None


@pytest.mark.asyncio
async def test_最新履歴取得_資格が有効なら_有効な候補を返す() -> None:
    # Arrange
    fixture = _Fixture(valid=True)
    fixture.register_references()
    usage = await fixture.save_usage()

    # Act
    actual = await fixture.use_case.execute(fixture.build_query())

    # Assert
    assert actual is not None
    assert (actual.usage.id, actual.is_still_valid) == (str(usage.id.value), True)


@pytest.mark.asyncio
async def test_最新履歴取得_資格が無効なら_無効フラグ付きで候補を返す() -> None:
    # Arrange
    fixture = _Fixture(valid=False)
    fixture.register_references()
    usage = await fixture.save_usage()

    # Act
    actual = await fixture.use_case.execute(fixture.build_query())

    # Assert
    # 候補自体は返すが、自動適用してはならないことをフラグで区別できる。
    assert actual is not None
    assert (actual.usage.id, actual.is_still_valid) == (str(usage.id.value), False)


@pytest.mark.asyncio
async def test_最新履歴取得_再検証は_クエリの適用日で行われる() -> None:
    # Arrange
    fixture = _Fixture(valid=True)
    fixture.register_references()
    await fixture.save_usage()

    # Act
    await fixture.use_case.execute(fixture.build_query())

    # Assert
    assert fixture.coverage_validity.calls == [
        (fixture.corporate_id, fixture.patient_id, _APPLIED_ON)
    ]


@pytest.mark.asyncio
async def test_最新履歴取得_他法人の店舗を指定すると_店舗未存在エラーになる() -> None:
    # Arrange
    fixture = _Fixture(valid=True)
    fixture.patient_reference.register(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
    )
    # 店舗は別法人にだけ存在させる。
    fixture.store_reference.register(
        corporate_id=CorporateId.generate(),
        store_id=fixture.store_id,
    )

    # Act / Assert
    with pytest.raises(ClaimStoreNotFoundError):
        await fixture.use_case.execute(fixture.build_query())


@pytest.mark.asyncio
async def test_最新履歴取得_他法人の患者を指定すると_患者未存在エラーになる() -> None:
    # Arrange
    fixture = _Fixture(valid=True)
    fixture.store_reference.register(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
    )
    # 患者は別法人にだけ存在させる。
    fixture.patient_reference.register(
        corporate_id=CorporateId.generate(),
        patient_id=fixture.patient_id,
    )

    # Act / Assert
    with pytest.raises(ClaimPatientNotFoundError):
        await fixture.use_case.execute(fixture.build_query())
