"""適用資格利用履歴の記録ユースケースのテスト。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.claim.exceptions import (
    ClaimCoverageSelectionError,
    ClaimPatientNotFoundError,
    ClaimStoreNotFoundError,
)
from app.application.claim.record_coverage_usage import (
    RecordCoverageUsageCommand,
    RecordCoverageUsageUseCase,
)
from app.domain.claim.coverage_snapshot import (
    CoverageSnapshot,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.claim.primitives import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.claim_reference_boundaries import (
    FakeCoverageSnapshotSource,
    FakePatientReference,
    FakeStoreReference,
)
from tests.fakes.in_memory_coverage_usage_repository import (
    InMemoryCoverageUsageRepository,
)

_JST = timezone(timedelta(hours=9))
_COVERAGE_IDS = ("coverage-1", "coverage-2")


def _create_snapshot() -> CoverageSnapshot:
    """医療保険1件と第一公費のスナップショットを生成する。"""
    return CoverageSnapshot(
        insurance=InsuranceCoverageSnapshot(
            insurer_number=ClaimInsurerNumber("01130012"),
            insured_symbol=ClaimCoverageSymbol("A"),
            insured_number=ClaimCoverageCode("456"),
            insured_type=ClaimCoverageInsuredType.SELF,
            benefit_ratio=ClaimCoverageBenefitRatio(70),
        ),
        public_expenses=(
            PublicExpenseCoverageSnapshot(
                priority=ClaimCoveragePriority(1),
                payer_number=ClaimPublicPayerNumber("12345678"),
                recipient_number=ClaimPublicRecipientNumber("1234567"),
            ),
        ),
    )


class _Fixture:
    """ユースケースと依存フェイクをまとめて保持するテスト用の器。"""

    def __init__(self) -> None:
        self.corporate_id = CorporateId.generate()
        self.store_id = StoreId.generate()
        self.patient_id = PatientId.generate()
        self.repository = InMemoryCoverageUsageRepository()
        self.store_reference = FakeStoreReference()
        self.patient_reference = FakePatientReference()
        self.snapshot_source = FakeCoverageSnapshotSource()
        self.use_case = RecordCoverageUsageUseCase(
            self.repository,
            create_vendor_corporate_access(),
            self.store_reference,
            self.patient_reference,
            self.snapshot_source,
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

    def build_command(
        self,
        *,
        applied_at: datetime | None = None,
        coverage_ids: tuple[str, ...] = _COVERAGE_IDS,
    ) -> RecordCoverageUsageCommand:
        """テスト対象のコマンドを組み立てる。"""
        return RecordCoverageUsageCommand(
            corporate_id=str(self.corporate_id.value),
            store_id=str(self.store_id.value),
            patient_id=str(self.patient_id.value),
            applied_at=applied_at
            if applied_at is not None
            else datetime(2026, 8, 17, 12, 30, tzinfo=_JST),
            coverage_ids=coverage_ids,
        )


@pytest.mark.asyncio
async def test_利用履歴記録_選択した資格を_スナップショットとして保存する() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.register_references()
    fixture.snapshot_source.register(
        coverage_ids=_COVERAGE_IDS,
        snapshot=_create_snapshot(),
    )

    # Act
    actual = await fixture.use_case.execute(fixture.build_command())

    # Assert
    assert actual.snapshot.insurance is not None
    assert (
        actual.snapshot.insurance.insurer_number,
        actual.snapshot.insurance.benefit_ratio,
        [item.priority for item in actual.snapshot.public_expenses],
    ) == ("01130012", 70, [1])


@pytest.mark.asyncio
async def test_利用履歴記録_JSTの適用日時は_UTC表現で保存される() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.register_references()
    fixture.snapshot_source.register(
        coverage_ids=_COVERAGE_IDS,
        snapshot=_create_snapshot(),
    )

    # Act
    actual = await fixture.use_case.execute(fixture.build_command())

    # Assert
    assert actual.applied_at == "2026-08-17T03:30:00+00:00"


@pytest.mark.asyncio
async def test_利用履歴記録_保存後は_最新履歴として取得できる() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.register_references()
    fixture.snapshot_source.register(
        coverage_ids=_COVERAGE_IDS,
        snapshot=_create_snapshot(),
    )
    recorded = await fixture.use_case.execute(fixture.build_command())

    # Act
    actual = await fixture.repository.get_latest(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )

    # Assert
    assert actual is not None and str(actual.id.value) == recorded.id


@pytest.mark.asyncio
async def test_利用履歴記録_選択できない資格を指定すると_選択エラーになる() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.register_references()

    # Act / Assert
    with pytest.raises(ClaimCoverageSelectionError):
        await fixture.use_case.execute(
            fixture.build_command(coverage_ids=("unknown-coverage",))
        )


@pytest.mark.asyncio
async def test_利用履歴記録_他法人の店舗を指定すると_店舗未存在エラーになる() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.patient_reference.register(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
    )
    fixture.store_reference.register(
        corporate_id=CorporateId.generate(),
        store_id=fixture.store_id,
    )

    # Act / Assert
    with pytest.raises(ClaimStoreNotFoundError):
        await fixture.use_case.execute(fixture.build_command())


@pytest.mark.asyncio
async def test_利用履歴記録_他法人の患者を指定すると_患者未存在エラーになる() -> None:
    # Arrange
    fixture = _Fixture()
    fixture.store_reference.register(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
    )
    fixture.patient_reference.register(
        corporate_id=CorporateId.generate(),
        patient_id=fixture.patient_id,
    )

    # Act / Assert
    with pytest.raises(ClaimPatientNotFoundError):
        await fixture.use_case.execute(fixture.build_command())
