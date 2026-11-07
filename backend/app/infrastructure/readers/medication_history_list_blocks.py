"""薬歴ブロック一覧を投影するアダプタ。"""

from __future__ import annotations

from app.application.medication_history.interfaces.list_medication_history_blocks_query_reader import (
    ListMedicationHistoryBlocksQueryReader,
)
from app.application.medication_history.queries.dtos.medication_history_block import (
    MedicationHistoryBlockDto,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoryBlocksQuery,
)
from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
)


class ListMedicationHistoryBlocksProjection(ListMedicationHistoryBlocksQueryReader):
    """Repositoryから薬歴ブロック一覧を取得・投影する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        catalog_repository: MedicationHistoryCategoryCatalogRepository,
    ) -> None:
        self._repository = repository
        self._catalog_repository = catalog_repository

    async def read(
        self, query: ListMedicationHistoryBlocksQuery
    ) -> tuple[MedicationHistoryBlockDto, ...]:
        parsed_corporate_id = CorporateId.parse(query.corporate_id)
        parsed_record_id = MedicationHistoryRecordId.parse(query.record_id)

        record = await self._repository.get(
            corporate_id=parsed_corporate_id,
            record_id=parsed_record_id,
        )
        if record is None:
            record = await self._repository.get_by_event(
                corporate_id=parsed_corporate_id,
                event_id=EventId(parsed_record_id.value),
            )
        if record is None:
            return ()

        catalog = await self._catalog_repository.get(corporate_id=parsed_corporate_id)
        if catalog is None:
            catalog = MedicationHistoryCategoryCatalog.create_default(
                corporate_id=parsed_corporate_id
            )

        medium_map = {m.code.value: m.name.value for m in catalog.medium_categories}

        sorted_blocks = sorted(record.blocks, key=lambda b: b.display_order.value)

        return tuple(
            MedicationHistoryBlockDto(
                id=str(b.id.value),
                category_code=b.category_code.value,
                category_name=medium_map.get(
                    b.category_code.value, b.category_code.value
                ),
                category_badge_label=medium_map.get(
                    b.category_code.value, b.category_code.value
                ),
                content=b.content.value,
                display_order=b.display_order.value,
                source_module=b.source_module.value,
                source_id=b.source_id.value if b.source_id is not None else None,
                updated_by=str(b.updated_by.value)
                if b.updated_by is not None
                else None,
                updated_by_name="",
                updated_at=b.updated_at,
            )
            for b in sorted_blocks
        )


__all__ = ["ListMedicationHistoryBlocksProjection"]
