"""業務Eventの参照Boundaryアダプタを検証する。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.composition.care_event_references import (
    EventMedicationHistoryReferenceAdapter,
    EventPatientReferenceAdapter,
    EventReceptionReferenceAdapter,
    MedicationHistoryEventReferenceAdapter,
)
from app.domain.care_event.event import Event
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventId,
    EventOccurredTimestamp,
    EventTypeId,
    EventTypeName,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import (
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.reception.reception import Reception
from app.domain.store.primitives import StoreId
from tests.factories.medication_history_factory import create_record
from tests.factories.persistence_factory import create_patient
from tests.fakes.in_memory_event_repository import InMemoryEventRepository
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository
from tests.fakes.in_memory_reception_repository import InMemoryReceptionRepository


def _create_reception(
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    patient_id: PatientId,
    reception_id: ReceptionId | None = None,
    prescription_id: PrescriptionId | None = None,
    dispensing_id: DispensingId | None = None,
    event_id: EventId | None = None,
) -> Reception:
    return Reception(
        id=reception_id or ReceptionId.generate(),
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        latest_fingerprint=ReceptionFingerprint("a" * 64),
        field_fingerprints=(),
        prescription_id=prescription_id,
        dispensing_id=dispensing_id,
        event_id=event_id,
    )


async def test_EventPatientReferenceAdapter_患者存在確認() -> None:
    repo = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = create_patient(corporate_id=corporate_id)
    repo.items[patient.id] = patient
    adapter = EventPatientReferenceAdapter(repo)

    await adapter.require_exists(corporate_id=corporate_id, patient_id=patient.id)

    with pytest.raises(TenantBoundaryNotFoundError):
        await adapter.require_exists(
            corporate_id=corporate_id, patient_id=PatientId.generate()
        )
    with pytest.raises(TenantBoundaryNotFoundError):
        await adapter.require_exists(
            corporate_id=CorporateId.generate(), patient_id=patient.id
        )


async def test_EventMedicationHistoryReferenceAdapter_薬歴ID取得() -> None:
    repo = InMemoryMedicationHistoryRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    event_id = EventId.generate()
    record = create_record(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        event_id=event_id,
    )
    await repo.save(record)
    adapter = EventMedicationHistoryReferenceAdapter(repo)

    found_id = await adapter.get_id(corporate_id=corporate_id, event_id=event_id)
    assert found_id == str(record.id.value)

    not_found = await adapter.get_id(
        corporate_id=corporate_id, event_id=EventId.generate()
    )
    assert not_found is None


async def test_EventReceptionReferenceAdapter_処方と調剤IDの省略や不一致を拒否する() -> (
    None
):
    repo = InMemoryReceptionRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    prescription_id = PrescriptionId.generate()
    dispensing_id = DispensingId.generate()

    reception = _create_reception(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        prescription_id=prescription_id,
        dispensing_id=dispensing_id,
    )
    repo.items[(corporate_id, store_id, reception.id)] = reception
    adapter = EventReceptionReferenceAdapter(repo)

    # Receptionに処方箋があるのにEvent側で省略（None）すると拒否
    with pytest.raises(DomainError, match="処方箋が一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=None,
            dispensing_id=dispensing_id,
        )

    # Receptionに調剤があるのにEvent側で省略（None）すると拒否
    with pytest.raises(DomainError, match="調剤セッションが一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=prescription_id,
            dispensing_id=None,
        )

    # 処方箋ID不一致
    with pytest.raises(DomainError, match="処方箋が一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=PrescriptionId.generate(),
            dispensing_id=dispensing_id,
        )

    # 調剤ID不一致
    with pytest.raises(DomainError, match="調剤セッションが一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=prescription_id,
            dispensing_id=DispensingId.generate(),
        )

    # 完全一致なら成立
    await adapter.validate_reference(
        corporate_id=corporate_id,
        store_id=store_id,
        reception_id=reception.id,
        patient_id=patient_id,
        prescription_id=prescription_id,
        dispensing_id=dispensing_id,
    )


async def test_EventReceptionReferenceAdapter_Reception未所持のID付与を拒否する() -> (
    None
):
    repo = InMemoryReceptionRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()

    # 処方・調剤を持たない受付
    reception = _create_reception(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        prescription_id=None,
        dispensing_id=None,
    )
    repo.items[(corporate_id, store_id, reception.id)] = reception
    adapter = EventReceptionReferenceAdapter(repo)

    with pytest.raises(DomainError, match="処方箋が一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=PrescriptionId.generate(),
            dispensing_id=None,
        )

    with pytest.raises(DomainError, match="調剤セッションが一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception.id,
            patient_id=patient_id,
            prescription_id=None,
            dispensing_id=DispensingId.generate(),
        )

    # 双方Noneなら成立
    await adapter.validate_reference(
        corporate_id=corporate_id,
        store_id=store_id,
        reception_id=reception.id,
        patient_id=patient_id,
        prescription_id=None,
        dispensing_id=None,
    )


async def test_EventReceptionReferenceAdapter_既関連付けや患者不一致() -> None:
    repo = InMemoryReceptionRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()

    associated = _create_reception(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        event_id=EventId.generate(),
    )
    repo.items[(corporate_id, store_id, associated.id)] = associated
    adapter = EventReceptionReferenceAdapter(repo)

    with pytest.raises(DomainError, match="すでにEventが関連付いています"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=associated.id,
            patient_id=patient_id,
            prescription_id=None,
            dispensing_id=None,
        )

    unassociated = _create_reception(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
    )
    repo.items[(corporate_id, store_id, unassociated.id)] = unassociated

    with pytest.raises(DomainError, match="患者が一致しません"):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=unassociated.id,
            patient_id=PatientId.generate(),
            prescription_id=None,
            dispensing_id=None,
        )

    with pytest.raises(TenantBoundaryNotFoundError):
        await adapter.validate_reference(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=ReceptionId.generate(),
            patient_id=patient_id,
            prescription_id=None,
            dispensing_id=None,
        )


async def test_EventReceptionReferenceAdapter_Event関連付け保存() -> None:
    repo = InMemoryReceptionRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    reception = _create_reception(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
    )
    repo.items[(corporate_id, store_id, reception.id)] = reception
    adapter = EventReceptionReferenceAdapter(repo)

    event_id = EventId.generate()
    await adapter.associate_event(
        corporate_id=corporate_id,
        store_id=store_id,
        reception_id=reception.id,
        event_id=event_id,
    )

    saved = repo.items[(corporate_id, store_id, reception.id)]
    assert saved.event_id == event_id


async def test_MedicationHistoryEventReferenceAdapter_Event発生情報解決() -> None:
    repo = InMemoryEventRepository()
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()
    occurred_at = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    created_at = datetime(2026, 9, 20, 10, 5, tzinfo=UTC)

    event = Event.create(
        event_type_id=EventTypeId.generate(),
        event_type_name=EventTypeName("来局相談"),
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        occurred_at=EventOccurredTimestamp(occurred_at),
        created_at=EventCreatedTimestamp(created_at),
    )
    await repo.save(event)
    adapter = MedicationHistoryEventReferenceAdapter(repo)

    ref = await adapter.get(corporate_id=corporate_id, event_id=event.id)
    assert ref is not None
    assert ref.occurred_at == EventOccurredTimestamp(occurred_at)
    assert ref.event_type_name == EventTypeName("来局相談")

    missing = await adapter.get(corporate_id=CorporateId.generate(), event_id=event.id)
    assert missing is None
