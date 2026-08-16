from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise, to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    StoreId,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StoreNames,
)
from app.domain.store.repository import StoreRepository
from app.domain.store.services import StoreNameUniquenessService


@dataclass(frozen=True, kw_only=True)
class ChangeStoreNamesCommand:
    """店舗名変更に必要な入力データ（DTO）"""

    corporate_id: str
    store_id: str
    new_name: str
    new_name_kana: str
    new_romaji: str | None = None


class ChangeStoreNamesUseCase:
    """店舗名変更ユースケース"""

    def __init__(
        self,
        repository: StoreRepository,
        uniqueness_service: StoreNameUniquenessService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStoreNamesCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )
        store_id = StoreId.parse(command.store_id)

        raw_romaji = to_optional_text(command.new_romaji)
        new_store_names = StoreNames(
            name=StoreName(command.new_name),
            kana=StoreNameKana(command.new_name_kana),
            romaji=StoreNameRomaji(raw_romaji) if raw_romaji else None,
        )

        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )

        if store.names == new_store_names:
            return

        if store.names.name != new_store_names.name:
            await self._uniqueness_service.ensure_name_is_unique(
                corporate_id=corporate_id,
                name=new_store_names.name,
                excluding_id=store_id,
            )

        store = store.change_names(new_store_names)
        await self._repository.save(store)
