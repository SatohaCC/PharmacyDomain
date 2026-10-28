"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.medication_history.interfaces.get_medication_history_query_reader import (
    GetMedicationHistoryQueryReader,
)
from app.application.medication_history.interfaces.references import (
    MedicationHistoryEventBoundary,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.queries.models import GetMedicationHistoryQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.infrastructure.readers.helpers.medication_history_support import (
    load_record_or_raise,
)


class GetMedicationHistoryProjection(GetMedicationHistoryQueryReader):
    """法人境界を確認して薬歴を取得する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        event_reference: MedicationHistoryEventBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._event_reference = event_reference

    async def read(self, query: GetMedicationHistoryQuery) -> MedicationHistoryDto:
        """指定法人の薬歴をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        event = (
            await self._event_reference.get(
                corporate_id=corporate_id, event_id=record.event_id
            )
            if self._event_reference is not None
            else None
        )
        return MedicationHistoryDto.from_entity(record, event=event)
