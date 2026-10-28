"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.medication_history.interfaces.list_medication_histories_by_patient_query_reader import (
    ListMedicationHistoriesByPatientQueryReader,
)
from app.application.medication_history.interfaces.references import (
    MedicationHistoryEventBoundary,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoriesQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.patient.identifiers import PatientId


class ListMedicationHistoriesByPatientProjection(
    ListMedicationHistoriesByPatientQueryReader
):
    """患者の薬歴を服薬指導日時の昇順で返す。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        event_reference: MedicationHistoryEventBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._event_reference = event_reference

    async def read(
        self, query: ListMedicationHistoriesQuery
    ) -> tuple[MedicationHistoryDto, ...]:
        """指定法人・患者の薬歴をDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        records = await self._repository.list_by_patient(
            corporate_id=corporate_id, patient_id=PatientId.parse(query.patient_id)
        )
        result: list[MedicationHistoryDto] = []
        for record in records:
            event = (
                await self._event_reference.get(
                    corporate_id=corporate_id, event_id=record.event_id
                )
                if self._event_reference is not None
                else None
            )
            result.append(MedicationHistoryDto.from_entity(record, event=event))
        return tuple(result)
