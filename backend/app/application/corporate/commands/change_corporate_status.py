"""Applicationのchange_corporate_statusを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.common.organization_lock import OrganizationLock
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.repositories import CorporateRepository


@dataclass(frozen=True, kw_only=True)
class ChangeCorporateStatusCommand:
    """法人状態変更に必要な入力データ。"""

    corporate_id: str
    is_active: bool


class ChangeCorporateStatusUseCase:
    """ベンダーシステム管理者が法人の利用状態を変更するユースケース。"""

    def __init__(
        self,
        repository: CorporateRepository,
        corporate_access: CorporateAccessService,
        lock: OrganizationLock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._lock = lock

    async def execute(self, command: ChangeCorporateStatusCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        self._corporate_access.require_permission(
            corporate_id=corporate_id, permission=Permission.MANAGE_CORPORATE_STATUS
        )
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        corporate = await self._corporate_access.require_existing(
            corporate_id=corporate_id, permission=Permission.MANAGE_CORPORATE_STATUS
        )
        updated = corporate.activate() if command.is_active else corporate.deactivate()
        if updated.status == corporate.status:
            return
        await self._repository.save(updated)
