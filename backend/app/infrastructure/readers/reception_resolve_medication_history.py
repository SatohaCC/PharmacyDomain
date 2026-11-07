"""受付に紐づく薬歴IDまたはEvent IDを投影するアダプタ。"""

from __future__ import annotations

from app.application.common.exceptions import NotFoundError
from app.application.reception.interfaces.resolve_reception_medication_history_query_reader import (
    ResolveReceptionMedicationHistoryQueryReader,
)
from app.application.reception.queries.models import (
    ResolveReceptionMedicationHistoryQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.repositories import ReceptionRepository
from app.domain.store.identifiers import StoreId


class ResolveReceptionMedicationHistoryProjection(
    ResolveReceptionMedicationHistoryQueryReader
):
    """Repositoryから受付を取得し、薬歴IDまたはEvent IDを解決する。"""

    def __init__(self, reception_repository: ReceptionRepository) -> None:
        self._reception_repository = reception_repository

    async def read(self, query: ResolveReceptionMedicationHistoryQuery) -> str | None:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        reception_id = ReceptionId.parse(query.reception_id)

        reception = await self._reception_repository.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
        if reception is None:
            raise NotFoundError(
                "指定された受付が見つかりません。", code="RECEPTION_NOT_FOUND"
            )

        if reception.medication_history_id is not None:
            return str(reception.medication_history_id.value)
        if reception.event_id is not None:
            return str(reception.event_id.value)
        return None


__all__ = ["ResolveReceptionMedicationHistoryProjection"]
