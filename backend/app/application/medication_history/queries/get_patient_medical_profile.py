"""Applicationのget_patient_medical_profileを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
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


class GetPatientMedicalProfileUseCase:
    def __init__(
        self,
        reader: GetPatientMedicalProfileQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: GetPatientMedicalProfileQuery
    ) -> PatientMedicalProfileDto:
        """指定法人・患者の頭書きをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
        )
        return await self._reader.read(query)
