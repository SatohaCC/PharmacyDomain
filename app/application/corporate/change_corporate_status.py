"""法人の有効・無効状態を変更するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import Permission
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.corporate import CorporateId
from app.domain.corporate.repository import CorporateRepository


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
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeCorporateStatusCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        corporate = await self._corporate_access.require_existing(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_CORPORATE_STATUS,
        )

        updated = corporate.activate() if command.is_active else corporate.deactivate()
        if updated.status == corporate.status:
            return

        await self._repository.save(updated)
