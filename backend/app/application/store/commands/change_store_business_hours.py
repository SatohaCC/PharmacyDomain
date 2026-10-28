"""Applicationのchange_store_business_hoursを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.dtos.business_hours import BusinessHoursDto
from app.application.store.commands.models import ChangeStoreBusinessHoursCommand
from app.application.store.commands.services.business_hours import _build_hours
from app.application.store.commands.services.support import load_store_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


class ChangeStoreBusinessHoursUseCase:
    """開局時間をまとめて置き換える。"""

    def __init__(
        self, repository: StoreRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: ChangeStoreBusinessHoursCommand
    ) -> BusinessHoursDto:
        """週次の予定と特例日を置き換える。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=StoreId.parse(command.store_id),
        )
        hours = _build_hours(command)
        await self._repository.save(store.change_business_hours(hours))
        return BusinessHoursDto.from_value(hours)
