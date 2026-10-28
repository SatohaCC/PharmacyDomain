"""Applicationのlist_dispensings_by_prescriptionを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.dispensing.interfaces.list_dispensings_by_prescription_query_reader import (
    ListDispensingsByPrescriptionQueryReader,
)
from app.application.dispensing.queries.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.queries.models import ListDispensingsByPrescriptionQuery
from app.domain.corporate.identifiers import CorporateId


class ListDispensingsByPrescriptionUseCase:
    def __init__(
        self,
        reader: ListDispensingsByPrescriptionQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListDispensingsByPrescriptionQuery
    ) -> tuple[DispensingProcessDto, ...]:
        """指定法人・処方箋の調剤セッションをDTOで返す。

        リフィル・分割の各回は別の保険薬局で行われうるため、**返る件数は
        その処方箋の総調剤回数と一致しない**。
        呼び出し側が件数から回数を導出してはならない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_DISPENSING
        )
        return await self._reader.read(query)
