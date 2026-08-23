"""最新資格選択取得ユースケースのテスト。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from app.application.reception import (
    GetLastCoverageSelectionQuery,
    GetLastCoverageSelectionUseCase,
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
)
from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    InsuranceCoverageSnapshot,
)
from app.domain.corporate import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelection,
    CoverageSelectionRecord,
    OperatorPrincipalId,
    SelectedInsuranceSource,
    SourceCoverageId,
)
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.reception_reference_boundaries import (
    FakeCoverageValidity,
    FakePatientReference,
    FakeStoreReference,
)

_RECORDED_AT = datetime(2026, 8, 23, 3, 0, tzinfo=UTC)
_APPLIED_ON = date(2026, 8, 23)


@dataclass(frozen=True, kw_only=True)
class _Fixture:
    """ユースケースと、その依存へ手を入れるための参照一式。"""

    use_case: GetLastCoverageSelectionUseCase
    repository: InMemoryCoverageSelectionRecordRepository
    coverage_validity: FakeCoverageValidity
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId


def _create_selection(source_id: SourceCoverageId) -> CoverageSelection:
    """医療保険1件だけの選択を生成する。"""
    return CoverageSelection(
        insurance=SelectedInsuranceSource(
            source_coverage_id=source_id,
            values=InsuranceCoverageSnapshot(
                insurer_number=ClaimInsurerNumber("01130012"),
                insured_symbol=ClaimCoverageSymbol("A"),
                insured_number=ClaimCoverageCode("456"),
                insured_type=ClaimCoverageInsuredType.SELF,
                benefit_ratio=ClaimCoverageBenefitRatio(70),
            ),
        )
    )


def _create_fixture(*, valid: bool = True) -> _Fixture:
    """境界がすべて通る既定状態のユースケースを組み立てる。"""
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()

    repository = InMemoryCoverageSelectionRecordRepository()
    store_reference = FakeStoreReference()
    store_reference.register(corporate_id=corporate_id, store_id=store_id)
    patient_reference = FakePatientReference()
    patient_reference.register(corporate_id=corporate_id, patient_id=patient_id)
    coverage_validity = FakeCoverageValidity(valid=valid)

    return _Fixture(
        use_case=GetLastCoverageSelectionUseCase(
            repository=repository,
            corporate_access=create_vendor_corporate_access(),
            store_reference=store_reference,
            patient_reference=patient_reference,
            coverage_validity=coverage_validity,
        ),
        repository=repository,
        coverage_validity=coverage_validity,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
    )


async def _save_record(
    fixture: _Fixture,
    *,
    selection: CoverageSelection,
    recorded_at: datetime = _RECORDED_AT,
) -> CoverageSelectionRecord:
    """フィクスチャの法人・店舗・患者に対する履歴を保存する。"""
    record = CoverageSelectionRecord.create(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        applied_on=CoverageAppliedOn(date(2026, 8, 20)),
        selection=selection,
        recorded_at=CoverageRecordedAt(recorded_at),
        recorded_by=OperatorPrincipalId("operator-1"),
    )
    await fixture.repository.save(record)
    return record


def _create_query(fixture: _Fixture) -> GetLastCoverageSelectionQuery:
    """既定のフィクスチャに対応するクエリを生成する。"""
    return GetLastCoverageSelectionQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        patient_id=str(fixture.patient_id.value),
        applied_on=_APPLIED_ON,
    )


async def test_最新資格選択取得_履歴が無いと_Noneを返す() -> None:
    # Arrange
    fixture = _create_fixture()

    # Act
    actual = await fixture.use_case.execute(_create_query(fixture))

    # Assert
    assert actual is None


async def test_最新資格選択取得_選択を丸ごと再検証境界へ渡す() -> None:
    # Arrange
    fixture = _create_fixture()
    selection = _create_selection(SourceCoverageId.generate())
    await _save_record(fixture, selection=selection)

    # Act
    actual = await fixture.use_case.execute(_create_query(fixture))

    # Assert: 元IDとSnapshotへ分解せず、枠構造のまま照合させる
    assert actual is not None
    assert actual.is_still_valid is True
    assert fixture.coverage_validity.calls == [
        (fixture.corporate_id, fixture.patient_id, selection)
    ]


async def test_最新資格選択取得_再検証が偽なら_真正でない候補として返す() -> None:
    # Arrange
    fixture = _create_fixture(valid=False)
    await _save_record(
        fixture, selection=_create_selection(SourceCoverageId.generate())
    )

    # Act
    actual = await fixture.use_case.execute(_create_query(fixture))

    # Assert: 候補自体は返すが自動適用してはならないことを示す
    assert actual is not None
    assert actual.is_still_valid is False


async def test_最新資格選択取得_複数履歴があると_記録時刻が最新のものを返す() -> None:
    # Arrange
    fixture = _create_fixture()
    older_id, newer_id = SourceCoverageId.generate(), SourceCoverageId.generate()
    await _save_record(
        fixture,
        selection=_create_selection(older_id),
        recorded_at=_RECORDED_AT - timedelta(hours=1),
    )
    await _save_record(fixture, selection=_create_selection(newer_id))

    # Act
    actual = await fixture.use_case.execute(_create_query(fixture))

    # Assert
    assert actual is not None
    assert actual.record.selection.insurance is not None
    assert actual.record.selection.insurance.source_coverage_id == str(newer_id.value)


async def test_最新資格選択取得_別法人の店舗を指定すると_店舗未検出になる() -> None:
    # Arrange
    fixture = _create_fixture()
    query = GetLastCoverageSelectionQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(StoreId.generate().value),
        patient_id=str(fixture.patient_id.value),
        applied_on=_APPLIED_ON,
    )

    # Act / Assert
    with pytest.raises(ReceptionStoreNotFoundError):
        await fixture.use_case.execute(query)


async def test_最新資格選択取得_別法人の患者を指定すると_患者未検出になる() -> None:
    # Arrange
    fixture = _create_fixture()
    query = GetLastCoverageSelectionQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        patient_id=str(PatientId.generate().value),
        applied_on=_APPLIED_ON,
    )

    # Act / Assert
    with pytest.raises(ReceptionPatientNotFoundError):
        await fixture.use_case.execute(query)
