"""薬歴保存期限の患者単位更新とロック順序を検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.common.organization_lock import OrganizationLock
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
    FinalizeMedicationHistoryUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryRecordedTimestamp,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import create_fixture
from tests.factories.medication_history_factory import (
    create_record,
    finalize_record_with_review,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork


@pytest.mark.asyncio
async def test_tc40_06_07_患者内の最新確定記録へ全店舗の期限を延伸する() -> None:
    fixture = create_fixture()
    patient_id = fixture.patient_id
    store_a = fixture.store_id
    store_b = StoreId.generate()
    earlier_at = datetime(2024, 1, 10, 3, tzinfo=UTC)

    old_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=store_a,
            patient_id=patient_id,
            counselor_id=fixture.counselor_id,
            counseled_at=earlier_at,
        ),
        finalized_at=FinalizedTimestamp(earlier_at),
    )
    old_record = replace(old_record, retention_expiry_date=date(2027, 1, 10))

    new_record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=store_b,
        patient_id=patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=datetime(2026, 9, 20, 3, tzinfo=UTC),
    )
    new_record = replace(
        new_record,
        recorded_at=MedicationHistoryRecordedTimestamp(
            datetime(2026, 9, 23, 3, tzinfo=UTC)
        ),
    )

    another_patient_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            patient_id=PatientId.generate(),
            counselor_id=fixture.counselor_id,
        )
    )
    another_patient_record = replace(
        another_patient_record, retention_expiry_date=date(2030, 1, 1)
    )
    another_corporate_record = finalize_record_with_review(
        create_record(
            corporate_id=CorporateId.generate(),
            patient_id=patient_id,
            counselor_id=fixture.counselor_id,
        )
    )
    another_corporate_record = replace(
        another_corporate_record, retention_expiry_date=date(2031, 1, 1)
    )
    for record in (
        old_record,
        new_record,
        another_patient_record,
        another_corporate_record,
    ):
        await fixture.record_repository.save(record)

    fixture.clock.advance(datetime(2026, 9, 25, 3, tzinfo=UTC) - fixture.clock.now())
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(new_record.id.value),
            delay_reason="薬剤師の確認を経て後日確定した。",
            review_result="assessment_and_instruction_recorded",
        )
    )

    updated_old = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=old_record.id
    )
    updated_new = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=new_record.id
    )
    untouched_patient = await fixture.record_repository.get(
        corporate_id=fixture.corporate_id, record_id=another_patient_record.id
    )
    untouched_corporate = await fixture.record_repository.get(
        corporate_id=another_corporate_record.corporate_id,
        record_id=another_corporate_record.id,
    )

    assert updated_old is not None
    assert updated_new is not None
    assert updated_old.retention_expiry_date == date(2029, 9, 25)
    assert updated_new.retention_expiry_date == date(2029, 9, 25)
    assert fixture.record_repository.retention_expiry_update_calls == [
        (
            fixture.corporate_id,
            patient_id,
            {old_record.id: date(2029, 9, 25)},
        )
    ]
    assert untouched_patient is not None
    assert untouched_patient.retention_expiry_date == date(2030, 1, 1)
    assert untouched_corporate is not None
    assert untouched_corporate.retention_expiry_date == date(2031, 1, 1)


class _OrderedMedicationHistoryRepository(InMemoryMedicationHistoryRepository):
    """患者タイムラインと投影用全履歴読取の順序を記録する。"""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    async def list_by_patient(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> list[MedicationHistoryRecord]:
        self.events.append("patient_timeline")
        return await super().list_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )

    async def list_for_profile_projection(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> list[MedicationHistoryRecord]:
        last_lock_position = max(
            index for index, event in enumerate(self.events) if event == "patient_lock"
        )
        if "patient_timeline" not in self.events[last_lock_position + 1 :]:
            self.events.append("patient_timeline")
        else:
            self.events.append("profile_projection")
        return await super().list_for_profile_projection(
            corporate_id=corporate_id, patient_id=patient_id
        )


class _OrderedOrganizationLock(OrganizationLock):
    """要求キーと患者タイムライン読取との順序を記録する。"""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.keys: list[str] = []

    async def acquire(self, key: str) -> None:
        self.events.append("patient_lock")
        self.keys.append(key)


@pytest.mark.asyncio
async def test_tc40_08_患者ロックを同一法人患者で共有し読取より先に取る() -> None:
    fixture = create_fixture()
    events: list[str] = []
    repository = _OrderedMedicationHistoryRepository(events)
    lock = _OrderedOrganizationLock(events)
    use_case = FinalizeMedicationHistoryUseCase(
        record_repository=repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        category_catalog_repository=fixture.category_catalog_repository,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        clock=fixture.clock,
        organization_lock=lock,
    )
    target_patient_record = create_record(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=datetime(2026, 8, 23, 1, tzinfo=UTC),
    )
    same_scope_record = create_record(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=datetime(2026, 8, 23, 1, tzinfo=UTC),
    )
    other_patient_record = create_record(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.generate(),
        counselor_id=fixture.counselor_id,
        counseled_at=datetime(2026, 8, 23, 1, tzinfo=UTC),
    )
    for record in (target_patient_record, same_scope_record, other_patient_record):
        await repository.save(record)

    for record in (target_patient_record, same_scope_record, other_patient_record):
        await use_case.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(record.id.value),
                review_result="assessment_and_instruction_recorded",
            )
        )

    assert len(lock.keys) == 3
    assert lock.keys[0] == lock.keys[1]
    assert lock.keys[2] != lock.keys[0]
    lock_positions = [
        index for index, event in enumerate(events) if event == "patient_lock"
    ]
    timeline_positions = [
        index for index, event in enumerate(events) if event == "patient_timeline"
    ]
    projection_positions = [
        index for index, event in enumerate(events) if event == "profile_projection"
    ]
    assert len(lock_positions) == 3
    assert len(timeline_positions) == 3
    assert len(projection_positions) == 3
    for lock_position, timeline_position, projection_position in zip(
        lock_positions, timeline_positions, projection_positions, strict=True
    ):
        assert lock_position < timeline_position
        assert lock_position < projection_position
