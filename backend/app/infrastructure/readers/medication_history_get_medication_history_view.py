"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.medication_history.interfaces.get_medication_history_view_query_reader import (
    GetMedicationHistoryViewQueryReader,
)
from app.application.medication_history.interfaces.get_medication_history_view_reader import (
    CurrentPatientProfileBoundary,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.queries.dtos.get_medication_history_view import (
    MedicationHistoryViewDto,
)
from app.application.medication_history.queries.models import (
    GetMedicationHistoryViewQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.infrastructure.readers.helpers.medication_history_support import (
    load_record_or_raise,
)


class GetMedicationHistoryViewProjection(GetMedicationHistoryViewQueryReader):
    """薬歴と現行患者プロフィールを一緒に読む契約。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        patient_profile: CurrentPatientProfileBoundary,
    ) -> None:
        self._repository = repository
        self._patient_profile = patient_profile

    async def read(
        self, query: GetMedicationHistoryViewQuery
    ) -> MedicationHistoryViewDto:
        """薬歴本文と患者現行情報を認可後に返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        profile = await self._patient_profile.get_current_profile(
            corporate_id=corporate_id, patient_id=record.patient_id
        )
        if profile is None:
            raise TenantBoundaryNotFoundError()
        return MedicationHistoryViewDto(
            record=MedicationHistoryDto.from_entity(record),
            current_patient_profile=profile,
        )
