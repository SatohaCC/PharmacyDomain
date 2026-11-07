"""店舗の今回記載欄設定一覧を投影するアダプタ。"""

from __future__ import annotations

from app.application.medication_history.interfaces.list_store_current_record_fields_query_reader import (
    ListStoreCurrentRecordFieldsQueryReader,
)
from app.application.medication_history.queries.dtos.category_catalog import (
    CurrentRecordFieldDto,
)
from app.application.medication_history.queries.models import (
    ListStoreCurrentRecordFieldsQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
)
from app.domain.store.identifiers import StoreId


class ListStoreCurrentRecordFieldsProjection(ListStoreCurrentRecordFieldsQueryReader):
    """Repositoryから店舗に適用される今回記載欄項目一覧を取得・投影する。"""

    def __init__(self, repository: MedicationHistoryCategoryCatalogRepository) -> None:
        self._repository = repository

    async def read(
        self, query: ListStoreCurrentRecordFieldsQuery
    ) -> tuple[CurrentRecordFieldDto, ...]:
        parsed_corporate_id = CorporateId.parse(query.corporate_id)
        parsed_store_id = StoreId.parse(query.store_id)

        catalog = await self._repository.get(corporate_id=parsed_corporate_id)
        if catalog is None:
            catalog = MedicationHistoryCategoryCatalog.create_default(
                corporate_id=parsed_corporate_id
            )

        store_fields = [
            f
            for f in catalog.current_record_fields
            if f.store_id is None or f.store_id == parsed_store_id
        ]
        if not query.include_archived:
            store_fields = [f for f in store_fields if not f.is_archived]

        store_fields.sort(key=lambda f: f.display_order.value)

        medium_map = {m.code.value: m.name.value for m in catalog.medium_categories}
        return tuple(
            CurrentRecordFieldDto.from_value(
                f,
                badge_label=medium_map.get(f.category_code.value, "")
                if f.category_code is not None
                else "",
            )
            for f in store_fields
        )


__all__ = ["ListStoreCurrentRecordFieldsProjection"]
