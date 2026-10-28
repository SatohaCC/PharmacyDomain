"""Applicationのlist_patient_coveragesを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.coverage.interfaces.list_patient_coverages_query_reader import (
    ListPatientCoveragesQueryReader,
)
from app.application.coverage.interfaces.references import PatientReferenceBoundary
from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto,
)
from app.application.coverage.queries.models import ListPatientCoveragesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId


class ListPatientCoveragesUseCase:
    def __init__(
        self,
        reader: ListPatientCoveragesQueryReader,
        patient_reference: PatientReferenceBoundary,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._patient_reference = patient_reference
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListPatientCoveragesQuery
    ) -> list[PatientCoverageDto]:
        """法人・患者の存在を確認して資格一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_COVERAGE
        )
        patient_id = PatientId.parse(query.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return await self._reader.read(query)
