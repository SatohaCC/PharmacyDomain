"""薬歴記載ブロックの一括保存ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid7

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.common.clock import Clock
from app.application.common.exceptions import NotFoundError
from app.application.medication_history.commands.dtos.medication_history_block import (
    MedicationHistoryBlockDto,
)
from app.application.medication_history.commands.models import (
    MedicationHistoryBlockInput,
)
from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import (
    MedicationHistoryBlock,
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.identifiers import (
    MedicationHistoryBlockId,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.primitives import (
    BlockSourceId,
    BlockSourceModule,
    CategoryDisplayOrder,
    CounselingNote,
    MediumCategoryCode,
)
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
)
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class SaveMedicationHistoryBlocksCommand:
    """薬歴ブロック保存コマンド。"""

    corporate_id: str
    store_id: str
    record_id: str
    blocks: tuple[MedicationHistoryBlockInput, ...]
    staff_id: str | None = None


class SaveMedicationHistoryBlocksUseCase:
    """下書き薬歴のブロック群を一括で保存するユースケース。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        catalog_repository: MedicationHistoryCategoryCatalogRepository,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._catalog_repository = catalog_repository
        self._corporate_access = corporate_access
        self._store_operations = store_operations
        self._clock = clock

    async def execute(
        self, command: SaveMedicationHistoryBlocksCommand
    ) -> tuple[MedicationHistoryBlockDto, ...]:
        """下書き薬歴のブロック群を保存する。"""
        parsed_corporate_id = CorporateId.parse(command.corporate_id)
        parsed_store_id = StoreId.parse(command.store_id)
        parsed_record_id = MedicationHistoryRecordId.parse(command.record_id)

        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        await self._store_operations.require_allowed(
            corporate_id=parsed_corporate_id,
            store_id=parsed_store_id,
            operation=StoreOperation.START_HISTORY,
        )

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
            raise NotFoundError(f"薬歴 {command.record_id} が見つかりません。")

        catalog = await self._catalog_repository.get(corporate_id=parsed_corporate_id)
        if catalog is None:
            catalog = MedicationHistoryCategoryCatalog.create_default(
                corporate_id=parsed_corporate_id
            )
        category_map = {m.code.value: m for m in catalog.medium_categories}

        existing_by_id = {b.id.value: b for b in record.blocks}
        now = self._clock.now()
        staff_id = StaffId.parse(command.staff_id) if command.staff_id else None

        new_blocks: list[MedicationHistoryBlock] = []
        for input_block in command.blocks:
            category_code = MediumCategoryCode(input_block.category_code)
            display_order = CategoryDisplayOrder(input_block.display_order)
            source_module = BlockSourceModule(input_block.source_module)

            existing = (
                existing_by_id.get(MedicationHistoryBlockId.parse(input_block.id).value)
                if input_block.id
                else None
            )

            if existing is not None and existing.content.value == input_block.content:
                updated_by = existing.updated_by
                updated_at = existing.updated_at
            else:
                updated_by = (
                    staff_id
                    if staff_id is not None
                    else (existing.updated_by if existing else None)
                )
                updated_at = now

            block_id = (
                MedicationHistoryBlockId.parse(input_block.id)
                if input_block.id
                else MedicationHistoryBlockId(uuid7())
            )

            source_id = (
                BlockSourceId(input_block.source_id)
                if input_block.source_id is not None
                else (existing.source_id if existing else None)
            )

            new_blocks.append(
                MedicationHistoryBlock(
                    id=block_id,
                    category_code=category_code,
                    content=CounselingNote(input_block.content),
                    display_order=display_order,
                    source_module=source_module,
                    source_id=source_id,
                    updated_by=updated_by,
                    updated_at=updated_at,
                )
            )

        updated_record = record.update_blocks(tuple(new_blocks))
        await self._repository.save(updated_record)

        return tuple(
            MedicationHistoryBlockDto.from_domain(
                b,
                category_name=category_map[b.category_code.value].name.value
                if b.category_code.value in category_map
                else b.category_code.value,
                category_badge_label=category_map[b.category_code.value].name.value
                if b.category_code.value in category_map
                else b.category_code.value,
            )
            for b in updated_record.blocks
        )
