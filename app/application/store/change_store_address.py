"""店舗住所変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    StoreAddress,
    StoreAddressLine,
    StoreId,
    StorePostalCode,
)
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True, kw_only=True)
class ChangeStoreAddressCommand:
    """店舗住所変更に必要な入力データ（DTO）。"""

    corporate_id: str
    store_id: str
    postal_code: str
    address: str


class ChangeStoreAddressUseCase:
    """店舗住所変更ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStoreAddressCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )
        store_id = StoreId.parse(command.store_id)
        new_address = StoreAddress(
            postal_code=StorePostalCode(command.postal_code),
            address=StoreAddressLine(command.address),
        )

        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store.address == new_address:
            return

        store = store.change_address(new_address)
        await self._repository.save(store)
