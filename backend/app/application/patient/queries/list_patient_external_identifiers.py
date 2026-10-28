"""Applicationのlist_patient_external_identifiersを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.patient.interfaces.list_patient_external_identifiers_query_reader import (
    ListPatientExternalIdentifiersQueryReader,
)
from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import ListPatientExternalIdentifiersQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId


class ListPatientExternalIdentifiersUseCase:
    def __init__(
        self,
        reader: ListPatientExternalIdentifiersQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListPatientExternalIdentifiersQuery
    ) -> list[PatientExternalIdentifierDto]:
        """法人境界と患者の存在を確認して外部患者ID一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PATIENT
        )
        PatientId.parse(query.patient_id)
        return await self._reader.read(query)
