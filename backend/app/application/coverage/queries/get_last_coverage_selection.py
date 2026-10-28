"""Applicationのget_last_coverage_selectionを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.coverage.interfaces.get_last_coverage_selection_query_reader import (
    GetLastCoverageSelectionQueryReader,
)
from app.application.coverage.interfaces.references import (
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.application.coverage.queries.dtos.get_last_coverage_selection import (
    LastCoverageSelectionCandidateDto,
)
from app.application.coverage.queries.models import GetLastCoverageSelectionQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class GetLastCoverageSelectionUseCase:
    def __init__(
        self,
        reader: GetLastCoverageSelectionQueryReader,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference

    async def execute(
        self, query: GetLastCoverageSelectionQuery
    ) -> LastCoverageSelectionCandidateDto | None:
        """最新履歴があれば元IDと値を今回の適用日で再検証して返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_RECEPTION
        )
        store_id = StoreId.parse(query.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id, store_id=store_id
        )
        patient_id = PatientId.parse(query.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return await self._reader.read(query)
