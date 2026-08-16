"""法人単位の店舗一覧取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.store.repository import StoreCatalogRepository
from app.domain.store.store import Store


@dataclass(frozen=True, kw_only=True)
class ListStoresQuery:
    """店舗一覧取得の入力データ（DTO）。"""

    corporate_id: str


@dataclass(frozen=True, kw_only=True)
class StoreSummaryDto:
    """店舗一覧の出力データ（DTO）。"""

    id: str
    corporate_id: str
    name: str
    name_kana: str
    code: str | None

    @classmethod
    def from_entity(cls, store: Store) -> StoreSummaryDto:
        return cls(
            id=str(store.id.value),
            corporate_id=str(store.corporate_id.value),
            name=store.names.name.value,
            name_kana=store.names.kana.value,
            code=store.code.value if store.code else None,
        )


class ListStoresUseCase:
    """認可済みの対象法人に所属する店舗一覧を取得するユースケース。"""

    def __init__(
        self,
        repository: StoreCatalogRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: ListStoresQuery) -> list[StoreSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_STORE,
        )
        stores = await self._repository.list_by_corporate_id(corporate_id)
        return [StoreSummaryDto.from_entity(store) for store in stores]
