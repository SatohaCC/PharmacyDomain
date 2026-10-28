"""Applicationのlist_related_event_candidatesを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.care_event.interfaces.list_related_event_candidates_query_reader import (
    ListRelatedEventCandidatesQueryReader,
)
from app.application.care_event.interfaces.references import EventPatientBoundary
from app.application.care_event.queries.dtos.list_related_candidates import (
    RelatedEventCandidateDto,
)
from app.application.care_event.queries.models import ListRelatedEventCandidatesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class ListRelatedEventCandidatesUseCase:
    def __init__(
        self,
        reader: ListRelatedEventCandidatesQueryReader,
        patient_boundary: EventPatientBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._reader = reader
        self._patient_boundary = patient_boundary
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, query: ListRelatedEventCandidatesQuery
    ) -> tuple[RelatedEventCandidateDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        patient_id = PatientId.parse(query.patient_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_EVENT
        )
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.READ_HISTORY,
        )
        await self._patient_boundary.require_exists(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return await self._reader.read(query)
