"""店舗の今回記載欄設定を保存するコマンドユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.medication_history.commands.dtos.category_catalog import (
    CurrentRecordFieldDto,
)
from app.application.medication_history.commands.models import CurrentRecordFieldInput
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.identifiers import (
    CurrentRecordFieldId,
)
from app.domain.medication_history.primitives import (
    CategoryDisplayOrder,
    CurrentRecordFieldLabel,
    MediumCategoryCode,
)
from app.domain.medication_history.repositories import (
    MedicationHistoryCategoryCatalogRepository,
)
from app.domain.medication_history.value_objects import CurrentRecordFieldDefinition
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class SaveStoreCurrentRecordFieldsCommand:
    """店舗の今回記載欄設定の保存入力。"""

    corporate_id: str
    store_id: str
    fields: tuple[CurrentRecordFieldInput, ...]


class SaveStoreCurrentRecordFieldsUseCase:
    """店舗の今回記載欄設定を更新して保存する。"""

    def __init__(
        self,
        *,
        repository: MedicationHistoryCategoryCatalogRepository,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, command: SaveStoreCurrentRecordFieldsCommand
    ) -> tuple[CurrentRecordFieldDto, ...]:
        """指定店舗の今回記載欄設定を保存し、その店舗の設定一覧を返却する。"""
        parsed_corporate_id = CorporateId.parse(command.corporate_id)
        parsed_store_id = StoreId.parse(command.store_id)
        await self._corporate_access.require_active(
            corporate_id=parsed_corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        await self._store_operations.require_allowed(
            corporate_id=parsed_corporate_id,
            store_id=parsed_store_id,
            operation=StoreOperation.START_HISTORY,
        )

        catalog = await self._repository.get(corporate_id=parsed_corporate_id)
        if catalog is None:
            catalog = MedicationHistoryCategoryCatalog.create_default(
                corporate_id=parsed_corporate_id
            )

        # 既存の他店舗および法人共通のフィールドを保持し、対象店舗のフィールドを更新する
        other_fields = [
            f
            for f in catalog.current_record_fields
            if f.store_id is None or f.store_id != parsed_store_id
        ]

        store_new_fields = [
            CurrentRecordFieldDefinition(
                field_id=CurrentRecordFieldId.parse(item.id)
                if item.id
                else CurrentRecordFieldId.generate(),
                label=CurrentRecordFieldLabel(item.label),
                category_code=(
                    MediumCategoryCode(item.category_code)
                    if item.category_code
                    else None
                ),
                store_id=parsed_store_id,
                display_order=CategoryDisplayOrder(item.display_order),
                is_archived=item.is_archived,
            )
            for item in command.fields
        ]

        updated_catalog = catalog.update_current_record_fields(
            tuple(other_fields + store_new_fields)
        )
        await self._repository.save(updated_catalog)

        # 保存後の対象店舗の設定一覧を返す
        medium_map = {
            m.code.value: m.name.value for m in updated_catalog.medium_categories
        }
        active_store_fields = [
            f
            for f in updated_catalog.current_record_fields
            if f.store_id is None or f.store_id == parsed_store_id
        ]
        active_store_fields.sort(key=lambda f: f.display_order.value)

        return tuple(
            CurrentRecordFieldDto.from_value(
                f,
                badge_label=medium_map.get(f.category_code.value, "")
                if f.category_code is not None
                else "",
            )
            for f in active_store_fields
        )


__all__ = [
    "SaveStoreCurrentRecordFieldsCommand",
    "SaveStoreCurrentRecordFieldsUseCase",
]
