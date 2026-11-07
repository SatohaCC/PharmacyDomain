"""受付の今回記載欄入力値を投影するアダプタ。"""

from __future__ import annotations

from app.application.common.exceptions import NotFoundError
from app.application.reception.interfaces.get_current_record_values_query_reader import (
    GetCurrentRecordValuesQueryReader,
)
from app.application.reception.queries.dtos.current_record_values import (
    CurrentRecordFieldValueDto,
)
from app.application.reception.queries.models import GetCurrentRecordValuesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.repositories import ReceptionRepository
from app.domain.store.identifiers import StoreId


class GetCurrentRecordValuesProjection(GetCurrentRecordValuesQueryReader):
    """Repositoryから受付の今回記載欄入力値を取得・投影する。"""

    def __init__(self, reception_repository: ReceptionRepository) -> None:
        self._reception_repository = reception_repository

    async def read(
        self, query: GetCurrentRecordValuesQuery
    ) -> tuple[CurrentRecordFieldValueDto, ...]:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        reception_id = ReceptionId.parse(query.reception_id)

        reception = await self._reception_repository.get(
            corporate_id=corporate_id, store_id=store_id, reception_id=reception_id
        )
        if reception is None:
            raise NotFoundError(f"受付 {query.reception_id} が見つかりません。")

        return tuple(
            CurrentRecordFieldValueDto.from_value(v)
            for v in reception.current_record_values
        )


__all__ = ["GetCurrentRecordValuesProjection"]
