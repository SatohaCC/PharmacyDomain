"""店舗コード変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise, to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreCode, StoreId
from app.domain.store.repository import StoreRepository
from app.domain.store.services import StoreCodeUniquenessService


@dataclass(frozen=True, kw_only=True)
class ChangeStoreCodeCommand:
    """店舗コード変更に必要な入力データ（DTO）。"""

    corporate_id: str
    store_id: str
    #: ``None``・空文字・空白のみはいずれも店舗コードの解除を意味する。
    new_code: str | None


class ChangeStoreCodeUseCase:
    """店舗コード変更ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        uniqueness_service: StoreCodeUniquenessService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStoreCodeCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )
        store_id = StoreId.parse(command.store_id)
        raw_code = to_optional_text(command.new_code)
        new_code = StoreCode(raw_code) if raw_code else None

        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )

        if store.code == new_code:
            return

        if new_code is not None:
            await self._uniqueness_service.ensure_code_is_unique(
                corporate_id=corporate_id,
                code=new_code,
                excluding_id=store_id,
            )

        store = store.change_code(new_code)
        await self._repository.save(store)
