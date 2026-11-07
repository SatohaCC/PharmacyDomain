"""受付に紐づく薬歴IDまたはEvent IDを解決するクエリユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.reception.interfaces.resolve_reception_medication_history_query_reader import (
    ResolveReceptionMedicationHistoryQueryReader,
)
from app.application.reception.queries.models import (
    ResolveReceptionMedicationHistoryQuery,
)
from app.domain.corporate.identifiers import CorporateId


class ResolveReceptionMedicationHistoryUseCase:
    """受付の識別情報から関連付けられた薬歴IDまたはEvent IDを取得する。"""

    def __init__(
        self,
        *,
        reader: ResolveReceptionMedicationHistoryQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: ResolveReceptionMedicationHistoryQuery
    ) -> str | None:
        """受付の所属と権限を確認し、紐づく薬歴IDまたはEvent IDを文字列で返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)

        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_RECEPTION,
        )

        return await self._reader.read(query)


__all__ = [
    "ResolveReceptionMedicationHistoryQuery",
    "ResolveReceptionMedicationHistoryUseCase",
]
