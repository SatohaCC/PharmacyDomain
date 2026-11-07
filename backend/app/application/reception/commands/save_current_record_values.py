"""受付の今回記載欄入力値を保存するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import NotFoundError
from app.application.reception.commands.dtos.current_record_values import (
    CurrentRecordFieldValueDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import CurrentRecordFieldId
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import CurrentRecordFieldValueText
from app.domain.reception.repositories import ReceptionRepository
from app.domain.reception.value_objects import CurrentRecordFieldValue
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class SaveCurrentRecordValuesCommand:
    """受付の今回記載欄入力値の保存入力。"""

    corporate_id: str
    store_id: str
    reception_id: str
    values: tuple[CurrentRecordFieldValueDto, ...]


class SaveCurrentRecordValuesUseCase:
    """受付の今回記載欄入力値を保存する。"""

    def __init__(
        self,
        *,
        reception_repository: ReceptionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reception_repository = reception_repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: SaveCurrentRecordValuesCommand
    ) -> tuple[CurrentRecordFieldValueDto, ...]:
        """受付の今回記載欄入力値を更新して保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        store_id = StoreId.parse(command.store_id)
        reception_id = ReceptionId.parse(command.reception_id)

        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_RECEPTION
        )

        reception = await self._reception_repository.get(
            corporate_id=corporate_id, store_id=store_id, reception_id=reception_id
        )
        if reception is None:
            raise NotFoundError(f"受付 {command.reception_id} が見つかりません。")

        domain_values = tuple(
            CurrentRecordFieldValue(
                field_id=CurrentRecordFieldId.parse(v.field_id),
                value_text=CurrentRecordFieldValueText(v.value_text),
            )
            for v in command.values
        )

        updated_reception = reception.update_current_record_values(domain_values)
        await self._reception_repository.save(updated_reception)

        return tuple(
            CurrentRecordFieldValueDto.from_value(v)
            for v in updated_reception.current_record_values
        )


__all__ = [
    "SaveCurrentRecordValuesCommand",
    "SaveCurrentRecordValuesUseCase",
]
