"""薬歴から業務Eventを参照するRepository契約。"""

from app.domain.corporate.primitives import CorporateId
from tests.factories.medication_history_factory import create_record
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)


async def test_tc45_21_Eventから薬歴を引き法人境界を守る() -> None:
    repository = InMemoryMedicationHistoryRepository()
    corporate_id = CorporateId.generate()
    record = create_record(corporate_id=corporate_id)
    await repository.save(record)

    actual = await repository.get_by_event(
        corporate_id=corporate_id,
        event_id=record.event_id,
    )
    hidden = await repository.get_by_event(
        corporate_id=CorporateId.generate(),
        event_id=record.event_id,
    )

    assert actual is not None
    assert actual.id == record.id
    assert actual.event_id == record.event_id
    assert hidden is None
