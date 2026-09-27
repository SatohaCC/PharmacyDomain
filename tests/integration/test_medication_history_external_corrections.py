"""外部訂正の検索・下書き破棄をPostgreSQLで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    FinalizedTimestamp,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionDecision,
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
)
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_nsips_draft_record,
    create_record,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_with_event


@pytest.mark.asyncio
async def test_TC23_訂正一覧は法人店舗状態と複合カーソルをDBで絞る(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """DB検索は他店舗・他法人・解決済みを除外し、次ページで重複しない。"""
    corporate = create_corporate("訂正一覧法人")
    store = create_store(
        corporate_id=corporate.id,
        name="訂正一覧店舗A",
        kana="テイセイイチランテンポエー",
    )
    other_store = create_store(
        corporate_id=corporate.id,
        name="訂正一覧店舗B",
        kana="テイセイイチランテンポビー",
    )
    other_corporate = create_corporate("訂正一覧別法人")
    other_corporate_store = create_store(
        corporate_id=other_corporate.id,
        name="別法人店舗",
        kana="ベツホウジンテンポ",
    )
    patient = create_patient(corporate_id=corporate.id)
    other_patient = create_patient(corporate_id=other_corporate.id)
    now = datetime(2026, 9, 27, 3, tzinfo=UTC)

    def make_finalized_record(
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        correction_id: str,
    ) -> MedicationHistoryRecord:
        """検索境界ごとの確定薬歴を作る。"""
        draft = create_record(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            counselor_id=StaffId.generate(),
            counseled_at=COUNSELED_AT,
        )
        record = finalize_record_with_review(
            draft,
            finalized_at=FinalizedTimestamp(COUNSELED_AT),
            finalized_by=draft.counselor_id,
        )
        correction = ExternalPrescriptionCorrection(
            correction_id=correction_id,
            corrected_at=ExternalCorrectionTimestamp(now),
            source_document_number="DOC-EXTERNAL-CORRECTION",
            reason="外部訂正を受信した。",
        )
        return record.record_external_correction(correction)

    pending_one = make_finalized_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        correction_id="correction-a",
    )
    pending_two = make_finalized_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        correction_id="correction-b",
    )
    pending_three = make_finalized_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        correction_id="correction-c",
    )
    investigating = pending_two.review_external_correction(
        correction_id="correction-b",
        decision=ExternalCorrectionDecision.INVESTIGATING,
        reason="処方元へ照会中。",
        reviewed_by=StaffId.generate(),
        reviewed_at=ExternalCorrectionTimestamp(now),
    )
    resolved = pending_one.review_external_correction(
        correction_id="correction-a",
        decision=ExternalCorrectionDecision.NO_ACTION,
        reason="影響がないことを確認した。",
        reviewed_by=StaffId.generate(),
        reviewed_at=ExternalCorrectionTimestamp(now),
    )
    other_store_pending = make_finalized_record(
        corporate_id=corporate.id,
        store_id=other_store.id,
        patient_id=patient.id,
        correction_id="correction-store",
    )
    other_corporate_pending = make_finalized_record(
        corporate_id=other_corporate.id,
        store_id=other_corporate_store.id,
        patient_id=other_patient.id,
        correction_id="correction-corporate",
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        for tenant in (corporate, other_corporate):
            await repositories.corporate.save(tenant)
        for tenant_store in (store, other_store, other_corporate_store):
            await repositories.store.save(tenant_store)
        for tenant_patient in (patient, other_patient):
            await repositories.patient.save(tenant_patient)
        definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        if not any(
            item.standard_code is not None
            and item.standard_code.value == "prescription_reception"
            for item in definitions
        ):
            await repositories.event_definition.save(
                EventDefinition.create_standard(
                    code=EventTypeStandardCode("prescription_reception"),
                    name=EventTypeName("処方箋受付"),
                )
            )
        if not any(
            item.standard_code is not None
            and item.standard_code.value == "medication_period_follow_up"
            for item in definitions
        ):
            await repositories.event_definition.save(
                EventDefinition.create_standard(
                    code=EventTypeStandardCode("medication_period_follow_up"),
                    name=EventTypeName("服薬期間中フォローアップ"),
                )
            )
        for record in (
            resolved,
            investigating,
            pending_three,
            other_store_pending,
            other_corporate_pending,
        ):
            await save_history_with_event(repositories, record)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        first_page = await repository.list_external_corrections(
            corporate_id=corporate.id,
            store_id=store.id,
            statuses=(
                ExternalCorrectionStatus.PENDING,
                ExternalCorrectionStatus.INVESTIGATING,
            ),
            after=None,
            limit=1,
        )
        assert len(first_page) == 1
        first = first_page[0]
        second_page = await repository.list_external_corrections(
            corporate_id=corporate.id,
            store_id=store.id,
            statuses=(
                ExternalCorrectionStatus.PENDING,
                ExternalCorrectionStatus.INVESTIGATING,
            ),
            after=(str(first.record.id.value), first.correction.correction_id),
            limit=10,
        )

    found = [*first_page, *second_page]
    assert len(found) == 2
    assert {item.correction.status for item in found} == {
        ExternalCorrectionStatus.PENDING,
        ExternalCorrectionStatus.INVESTIGATING,
    }


@pytest.mark.asyncio
async def test_未指導DRAFTだけをPostgreSQLで破棄できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """条件付きDELETEは未指導下書きだけに一致し確定記録を保護する。"""
    corporate = create_corporate("下書き破棄法人")
    store = create_store(
        corporate_id=corporate.id,
        name="下書き破棄店舗",
        kana="シタガキハキテンポ",
    )
    patient = create_patient(corporate_id=corporate.id)
    unperformed = replace(
        create_nsips_draft_record(
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=patient.id,
        ),
        prescription_id=None,
        dispensing_id=None,
    )
    counseled = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        counselor_id=StaffId.generate(),
        counseled_at=COUNSELED_AT,
    )
    finalized_draft = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        counselor_id=StaffId.generate(),
        counseled_at=COUNSELED_AT,
    )
    finalized = finalize_record_with_review(
        finalized_draft,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=finalized_draft.counselor_id,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(corporate)
        await repositories.store.save(store)
        await repositories.patient.save(patient)
        definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        if not any(
            item.standard_code is not None
            and item.standard_code.value == "prescription_reception"
            for item in definitions
        ):
            await repositories.event_definition.save(
                EventDefinition.create_standard(
                    code=EventTypeStandardCode("prescription_reception"),
                    name=EventTypeName("処方箋受付"),
                )
            )
        await save_history_with_event(repositories, unperformed)
        await save_history_with_event(repositories, counseled)
        await save_history_with_event(repositories, finalized)
        assert (
            await repository.delete_unperformed_draft(
                corporate_id=corporate.id,
                record_id=unperformed.id,
            )
            is True
        )
        assert (
            await repository.delete_unperformed_draft(
                corporate_id=corporate.id,
                record_id=counseled.id,
            )
            is False
        )
        assert (
            await repository.delete_unperformed_draft(
                corporate_id=corporate.id,
                record_id=finalized.id,
            )
            is False
        )
        assert (
            await repository.get(corporate_id=corporate.id, record_id=unperformed.id)
            is None
        )
        assert (
            await repository.get(corporate_id=corporate.id, record_id=counseled.id)
            is not None
        )
        await work.commit()
