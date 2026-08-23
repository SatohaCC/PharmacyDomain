"""受付資格選択登録ユースケースのテスト。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from app.application.reception import (
    ReceptionCoverageSelectionError,
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
    RecordCoverageSelectionCommand,
    RecordCoverageSelectionUseCase,
)
from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.corporate import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception import (
    CoverageSelection,
    SelectedInsuranceSource,
    SelectedPublicExpenseSource,
    SourceCoverageId,
)
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.fake_clock import DEFAULT_NOW, FakeClock
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.reception_reference_boundaries import (
    FakeCoverageSelectionSource,
    FakePatientReference,
    FakeStoreReference,
)

_APPLIED_ON = date(2026, 8, 23)


@dataclass(frozen=True, kw_only=True)
class _Fixture:
    """ユースケースと、その依存へ手を入れるための参照一式。"""

    use_case: RecordCoverageSelectionUseCase
    repository: InMemoryCoverageSelectionRecordRepository
    store_reference: FakeStoreReference
    patient_reference: FakePatientReference
    coverage_selection: FakeCoverageSelectionSource
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId


def _create_selection(
    insurance_id: SourceCoverageId,
    public_id: SourceCoverageId,
) -> CoverageSelection:
    """医療保険1件と第一公費1件の選択を生成する。"""
    return CoverageSelection(
        insurance=SelectedInsuranceSource(
            source_coverage_id=insurance_id,
            values=InsuranceCoverageSnapshot(
                insurer_number=ClaimInsurerNumber("01130012"),
                insured_symbol=ClaimCoverageSymbol("A"),
                insured_number=ClaimCoverageCode("456"),
                insured_type=ClaimCoverageInsuredType.SELF,
                benefit_ratio=ClaimCoverageBenefitRatio(70),
            ),
        ),
        public_expenses=(
            SelectedPublicExpenseSource(
                source_coverage_id=public_id,
                values=PublicExpenseCoverageSnapshot(
                    priority=ClaimCoveragePriority(1),
                    payer_number=ClaimPublicPayerNumber("12345671"),
                    recipient_number=ClaimPublicRecipientNumber("1234561"),
                ),
            ),
        ),
    )


def _create_fixture() -> _Fixture:
    """境界がすべて通る既定状態のユースケースを組み立てる。"""
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()

    repository = InMemoryCoverageSelectionRecordRepository()
    store_reference = FakeStoreReference()
    store_reference.register(corporate_id=corporate_id, store_id=store_id)
    patient_reference = FakePatientReference()
    patient_reference.register(corporate_id=corporate_id, patient_id=patient_id)
    coverage_selection = FakeCoverageSelectionSource()

    return _Fixture(
        use_case=RecordCoverageSelectionUseCase(
            repository=repository,
            corporate_access=create_vendor_corporate_access(),
            store_reference=store_reference,
            patient_reference=patient_reference,
            coverage_selection=coverage_selection,
            clock=FakeClock(),
        ),
        repository=repository,
        store_reference=store_reference,
        patient_reference=patient_reference,
        coverage_selection=coverage_selection,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
    )


def _create_command(
    fixture: _Fixture, coverage_ids: tuple[str, ...]
) -> RecordCoverageSelectionCommand:
    """既定のフィクスチャに対応するコマンドを生成する。"""
    return RecordCoverageSelectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        patient_id=str(fixture.patient_id.value),
        applied_on=_APPLIED_ON,
        coverage_ids=coverage_ids,
    )


async def test_受付資格選択登録_医療保険と公費を選ぶと_枠ごとに元IDが保存される() -> (
    None
):
    # Arrange
    fixture = _create_fixture()
    insurance_id, public_id = SourceCoverageId.generate(), SourceCoverageId.generate()
    coverage_ids = (str(insurance_id.value), str(public_id.value))
    fixture.coverage_selection.register(
        coverage_ids=coverage_ids,
        selection=_create_selection(insurance_id, public_id),
    )

    # Act
    actual = await fixture.use_case.execute(_create_command(fixture, coverage_ids))

    # Assert
    assert actual.selection.insurance is not None
    assert actual.selection.insurance.source_coverage_id == str(insurance_id.value)
    assert len(actual.selection.public_expenses) == 1
    assert actual.selection.public_expenses[0].source_coverage_id == str(
        public_id.value
    )
    assert actual.selection.public_expenses[0].priority == 1


async def test_受付資格選択登録_登録すると_注入Clockの時刻と認可Actorが記録される() -> (
    None
):
    # Arrange
    fixture = _create_fixture()
    insurance_id, public_id = SourceCoverageId.generate(), SourceCoverageId.generate()
    coverage_ids = (str(insurance_id.value), str(public_id.value))
    fixture.coverage_selection.register(
        coverage_ids=coverage_ids,
        selection=_create_selection(insurance_id, public_id),
    )

    # Act
    actual = await fixture.use_case.execute(_create_command(fixture, coverage_ids))

    # Assert: 監査値はコマンドではなく依存から来る
    assert actual.recorded_at == DEFAULT_NOW.isoformat()
    assert actual.recorded_by == "test-vendor-admin"
    assert actual.applied_on == _APPLIED_ON.isoformat()


async def test_受付資格選択登録_保存すると_履歴が取得できる() -> None:
    # Arrange
    fixture = _create_fixture()
    insurance_id, public_id = SourceCoverageId.generate(), SourceCoverageId.generate()
    coverage_ids = (str(insurance_id.value), str(public_id.value))
    selection = _create_selection(insurance_id, public_id)
    fixture.coverage_selection.register(coverage_ids=coverage_ids, selection=selection)
    await fixture.use_case.execute(_create_command(fixture, coverage_ids))

    # Act
    stored = await fixture.repository.get_latest(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )

    # Assert: Fakeは選択を分解せず丸ごと保持する
    assert stored is not None
    assert stored.selection == selection


async def test_受付資格選択登録_別法人の店舗を指定すると_店舗未検出になる() -> None:
    # Arrange
    fixture = _create_fixture()
    command = RecordCoverageSelectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(StoreId.generate().value),
        patient_id=str(fixture.patient_id.value),
        applied_on=_APPLIED_ON,
        coverage_ids=(str(SourceCoverageId.generate().value),),
    )

    # Act / Assert: 他テナントの存在を隠すため404相当へ畳む
    with pytest.raises(ReceptionStoreNotFoundError):
        await fixture.use_case.execute(command)


async def test_受付資格選択登録_別法人の患者を指定すると_患者未検出になる() -> None:
    # Arrange
    fixture = _create_fixture()
    command = RecordCoverageSelectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        patient_id=str(PatientId.generate().value),
        applied_on=_APPLIED_ON,
        coverage_ids=(str(SourceCoverageId.generate().value),),
    )

    # Act / Assert
    with pytest.raises(ReceptionPatientNotFoundError):
        await fixture.use_case.execute(command)


async def test_受付資格選択登録_選択を構成できないと_選択エラーになる() -> None:
    # Arrange
    fixture = _create_fixture()
    command = _create_command(fixture, (str(SourceCoverageId.generate().value),))

    # Act / Assert: 資格の不在を例外の種類で区別して漏らさない
    with pytest.raises(ReceptionCoverageSelectionError):
        await fixture.use_case.execute(command)


async def test_受付資格選択登録_記録時刻は_タイムゾーン付きUTCで保存される() -> None:
    # Arrange
    fixture = _create_fixture()
    insurance_id, public_id = SourceCoverageId.generate(), SourceCoverageId.generate()
    coverage_ids = (str(insurance_id.value), str(public_id.value))
    fixture.coverage_selection.register(
        coverage_ids=coverage_ids,
        selection=_create_selection(insurance_id, public_id),
    )
    await fixture.use_case.execute(_create_command(fixture, coverage_ids))

    # Act
    stored = await fixture.repository.get_latest(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )

    # Assert
    assert stored is not None
    assert stored.recorded_at.value.tzinfo is not None
    assert stored.recorded_at.value == datetime(2026, 8, 23, 3, 0, tzinfo=UTC)
