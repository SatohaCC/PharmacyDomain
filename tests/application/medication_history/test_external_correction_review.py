"""外部処方訂正の一覧・判断Application契約を検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.exceptions import (
    MedicationHistoryNotFoundError,
)
from app.application.medication_history.list_pending_external_corrections import (
    ListPendingExternalCorrectionsQuery,
    ListPendingExternalCorrectionsUseCase,
)
from app.application.medication_history.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionCommand,
    ReviewExternalPrescriptionCorrectionUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    MedicationHistoryNotFinalizedError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    FinalizedTimestamp,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionDecision,
    ExternalCorrectionKind,
    ExternalPrescriptionCorrection,
)
from app.domain.staff.primitives import StaffQualifications
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_resolved_actor,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_record,
    finalize_record_with_review,
)
from tests.factories.prescription_factory import create_prescription
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)


def _pending_correction() -> ExternalPrescriptionCorrection:
    """確定薬歴に保留訂正を1件付ける。"""
    correction = ExternalPrescriptionCorrection(
        correction_id="corr-usecase-001",
        corrected_at=ExternalCorrectionTimestamp(
            datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
        ),
        source_document_number="RX-20260824-001",
        reason="NSIPS訂正受信",
        kind=ExternalCorrectionKind.UPDATE,
    )
    return correction


async def _stored_pending_record(
    fixture: MedicationHistoryFixture,
) -> MedicationHistoryRecord:
    """Application Fixtureに確定済み保留薬歴を保存する。"""
    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        dispensing_id=fixture.dispensing.id,
        prescription_id=fixture.dispensing.prescription_id,
        counseled_at=COUNSELED_AT,
    )
    record = finalize_record_with_review(
        draft,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=fixture.counselor_id,
    ).record_external_correction(_pending_correction())
    await fixture.record_repository.save(record)
    return record


@pytest.mark.asyncio
async def test_TC15_レビュー者と時刻はActorContextとClockから決まる() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    assert isinstance(fixture.actor, ResolvedActorContext)
    reviewer_id = fixture.actor.staff_id
    assert reviewer_id == fixture.counselor_id
    before = fixture.clock.now()
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="薬歴への影響がないことを確認した。",
    )

    await ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    ).execute(command)

    assert not hasattr(command, "reviewed_by")
    assert not hasattr(command, "reviewed_at")
    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    event = saved.external_corrections[0].review_events[-1]
    assert event.reviewed_by == reviewer_id
    assert event.reviewed_at.value == before


@pytest.mark.asyncio
async def test_TC16_STORE_VIEWERはレビュー操作を実行できない() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    viewer = create_resolved_actor(
        staff_id=fixture.counselor_id,
        role=ActorRole.STORE_VIEWER,
        corporate_id=fixture.corporate_id,
        store_ids=frozenset({fixture.store_id}),
    )
    access = CorporateAccessService(
        fixture.corporate_repository, AuthorizationService(viewer)
    )
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="権限境界の確認。",
    )

    with pytest.raises(AuthorizationError):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC20_未完了一覧は保留と調査中だけをページで返す() -> None:
    fixture = create_fixture()
    await _stored_pending_record(fixture)
    query = ListPendingExternalCorrectionsQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        limit=10,
    )

    page = await ListPendingExternalCorrectionsUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
    ).execute(query)

    assert len(page.items) == 1
    item = page.items[0]
    assert item.record_id
    assert item.correction_id == "corr-usecase-001"
    assert item.correction_status == "pending"
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_TC21_DRAFT薬歴は外部訂正レビュー対象にできない() -> None:
    fixture = create_fixture()
    draft = replace(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.counselor_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
            counseled_at=COUNSELED_AT,
        ),
        external_corrections=(_pending_correction(),),
    )
    await fixture.record_repository.save(draft)
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(draft.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="下書き拒否を確認。",
    )

    with pytest.raises(MedicationHistoryNotFinalizedError):
        await ReviewExternalPrescriptionCorrectionUseCase(
            repository=fixture.record_repository,
            corporate_access=fixture.corporate_access,
            staff_qualification=fixture.staff_qualification,
            prescription_repository=InMemoryPrescriptionRepository(),
            clock=fixture.clock,
        ).execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=draft.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC05_照合先の処方箋が別患者なら解決できない() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    other_patient_prescription = create_prescription(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
    )
    prescription_repository = InMemoryPrescriptionRepository()
    await prescription_repository.save(other_patient_prescription)
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION.value,
        reason="再登録処方との照合を確認する。",
        matched_prescription_id=str(other_patient_prescription.id.value),
    )

    with pytest.raises(NotFoundError):
        await ReviewExternalPrescriptionCorrectionUseCase(
            repository=fixture.record_repository,
            corporate_access=fixture.corporate_access,
            staff_qualification=fixture.staff_qualification,
            prescription_repository=prescription_repository,
            clock=fixture.clock,
        ).execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC05_同一患者の再登録処方と照合できる() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    matched_prescription = create_prescription(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )
    prescription_repository = InMemoryPrescriptionRepository()
    await prescription_repository.save(matched_prescription)
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION.value,
        reason="同じ患者の再登録処方を確認した。",
        matched_prescription_id=str(matched_prescription.id.value),
    )

    reviewed = await ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=prescription_repository,
        clock=fixture.clock,
    ).execute(command)

    assert reviewed.external_corrections[0].review_events[
        -1
    ].matched_prescription_id == (str(matched_prescription.id.value))


@pytest.mark.asyncio
async def test_TC17_スタッフ未解決Actorではレビューを実行できない() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    unresolved_actor = create_resolved_actor(
        staff_id=None,
        role=ActorRole.CORPORATE_ADMIN,
        corporate_id=fixture.corporate_id,
    )
    access = CorporateAccessService(
        fixture.corporate_repository, AuthorizationService(unresolved_actor)
    )
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="スタッフ未解決の検証。",
    )

    with pytest.raises(AuthorizationError):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC17_非薬剤師スタッフではレビューを実行できない() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    fixture.staff_qualification.register(
        corporate_id=fixture.corporate_id,
        staff_id=fixture.counselor_id,
        qualifications=StaffQualifications(),
    )
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="非薬剤師の検証。",
    )

    with pytest.raises(CounselorQualificationError):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC18_別法人の薬歴は存在を隠蔽して404とする() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    other_corporate_id = CorporateId.generate()
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(other_corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="別法人アクセスの検証。",
    )

    with pytest.raises(MedicationHistoryNotFoundError):
        await use_case.execute(command)


@pytest.mark.asyncio
async def test_TC18_担当外店舗の薬歴は権限エラーで変更させない() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    other_store_id = StoreId.generate()
    store_operator = create_resolved_actor(
        staff_id=fixture.counselor_id,
        role=ActorRole.STORE_OPERATOR,
        corporate_id=fixture.corporate_id,
        store_ids=frozenset({other_store_id}),
    )
    access = CorporateAccessService(
        fixture.corporate_repository, AuthorizationService(store_operator)
    )
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="担当外店舗アクセスの検証。",
    )

    with pytest.raises(TenantBoundaryNotFoundError):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC19_無効法人ではレビュー操作を拒否する() -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)
    fixture.corporate_repository.set_inactive(fixture.corporate_id)
    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="無効法人の検証。",
    )

    with pytest.raises(CorporateInactiveError):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.asyncio
async def test_TC22_保存失敗時は部分状態を返さず保存も成立しない(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = create_fixture()
    record = await _stored_pending_record(fixture)

    async def _failing_save(_entity: MedicationHistoryRecord) -> None:
        raise RuntimeError("永続化障害の注入。")

    monkeypatch.setattr(fixture.record_repository, "save", _failing_save)

    use_case = ReviewExternalPrescriptionCorrectionUseCase(
        repository=fixture.record_repository,
        corporate_access=fixture.corporate_access,
        staff_qualification=fixture.staff_qualification,
        prescription_repository=InMemoryPrescriptionRepository(),
        clock=fixture.clock,
    )
    command = ReviewExternalPrescriptionCorrectionCommand(
        corporate_id=str(fixture.corporate_id.value),
        record_id=str(record.id.value),
        correction_id="corr-usecase-001",
        decision=ExternalCorrectionDecision.NO_ACTION.value,
        reason="一括原子性の検証。",
    )

    with pytest.raises(RuntimeError, match="永続化障害の注入。"):
        await use_case.execute(command)

    saved = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()
