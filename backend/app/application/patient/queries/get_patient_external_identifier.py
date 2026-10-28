"""Applicationのget_patient_external_identifierを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.patient.interfaces.get_patient_external_identifier_query_reader import (
    GetPatientExternalIdentifierQueryReader,
)
from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import GetPatientExternalIdentifierQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientExternalIdentifierId


class GetPatientExternalIdentifierUseCase:
    def __init__(
        self,
        reader: GetPatientExternalIdentifierQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: GetPatientExternalIdentifierQuery
    ) -> PatientExternalIdentifierDto:
        """法人境界を確認して外部患者ID対応付けをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
        )
        PatientExternalIdentifierId.parse(query.identifier_id)
        return await self._reader.read(query)
