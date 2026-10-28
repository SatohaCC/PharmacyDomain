"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.medication_history.errors import PatientMedicalProfileNotFoundError
from app.application.medication_history.interfaces.get_patient_medical_profile_query_reader import (
    GetPatientMedicalProfileQueryReader,
)
from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    PatientMedicalProfileDto,
)
from app.application.medication_history.queries.models import (
    GetPatientMedicalProfileQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.repositories import PatientMedicalProfileRepository
from app.domain.patient.identifiers import PatientId


class GetPatientMedicalProfileProjection(GetPatientMedicalProfileQueryReader):
    """法人境界を確認して頭書きを取得する。"""

    def __init__(self, repository: PatientMedicalProfileRepository) -> None:
        self._repository = repository

    async def read(
        self, query: GetPatientMedicalProfileQuery
    ) -> PatientMedicalProfileDto:
        """指定法人・患者の頭書きをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        profile = await self._repository.get_by_patient(
            corporate_id=corporate_id, patient_id=PatientId.parse(query.patient_id)
        )
        if profile is None:
            raise PatientMedicalProfileNotFoundError()
        return PatientMedicalProfileDto.from_entity(profile, as_of=query.as_of)
