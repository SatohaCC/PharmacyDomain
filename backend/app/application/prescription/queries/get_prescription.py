"""Applicationのget_prescriptionを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.prescription.interfaces.get_prescription_query_reader import (
    GetPrescriptionQueryReader,
)
from app.application.prescription.queries.dtos.get_prescription import PrescriptionDto
from app.application.prescription.queries.models import GetPrescriptionQuery
from app.domain.corporate.identifiers import CorporateId


class GetPrescriptionUseCase:
    def __init__(
        self,
        reader: GetPrescriptionQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetPrescriptionQuery) -> PrescriptionDto:
        """指定法人の処方箋をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_PRESCRIPTION
        )
        return await self._reader.read(query)
