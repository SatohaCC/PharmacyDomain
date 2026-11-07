"""Applicationのget_patientを定義する。"""

from __future__ import annotations

from dataclasses import replace

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import AuthorizationError
from app.application.patient.interfaces.get_patient_query_reader import (
    GetPatientQueryReader,
)
from app.application.patient.queries.dtos.get_patient import PatientDto
from app.application.patient.queries.models import GetPatientQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId


class GetPatientUseCase:
    def __init__(
        self, reader: GetPatientQueryReader, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientQuery) -> PatientDto:
        """法人境界を確認して患者情報DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active_any(
            corporate_id=corporate_id,
            permissions=(Permission.VIEW_PATIENT, Permission.VIEW_PATIENT_HEADING),
        )
        PatientId.parse(query.patient_id)
        dto = await self._reader.read(query)

        has_ledger_access = True
        try:
            await self._corporate_access.require_active(
                corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
            )
        except AuthorizationError:
            has_ledger_access = False

        if not has_ledger_access and dto.profile_history:
            dto = replace(dto, profile_history=())
        return dto
