"""店舗詳細取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository
from app.domain.store.store import Store


@dataclass(frozen=True, kw_only=True)
class GetStoreQuery:
    """店舗詳細取得の入力データ（DTO）"""

    corporate_id: str
    store_id: str


@dataclass(frozen=True, kw_only=True)
class StoreDto:
    """店舗詳細の出力データ（DTO）"""

    id: str
    corporate_id: str
    name: str
    name_kana: str
    name_romaji: str | None
    postal_code: str
    address: str
    phone_number: str
    fax_number: str | None
    email: str | None
    code: str | None
    insurance_pharmacy_number: str | None

    @classmethod
    def from_entity(cls, store: Store) -> StoreDto:
        """Store エンティティから DTO を生成するファクトリメソッド"""
        return cls(
            id=str(store.id.value),
            corporate_id=str(store.corporate_id.value),
            name=store.names.name.value,
            name_kana=store.names.kana.value,
            name_romaji=store.names.romaji.value if store.names.romaji else None,
            postal_code=store.address.postal_code.value,
            address=store.address.address.value,
            phone_number=store.contact_info.phone_number.value,
            fax_number=(
                store.contact_info.fax_number.value
                if store.contact_info.fax_number
                else None
            ),
            email=(
                store.contact_info.email.value if store.contact_info.email else None
            ),
            code=store.code.value if store.code else None,
            insurance_pharmacy_number=(
                store.insurance_pharmacy_number.value
                if store.insurance_pharmacy_number
                else None
            ),
        )


class GetStoreUseCase:
    """店舗詳細取得ユースケース"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetStoreQuery) -> StoreDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_STORE,
        )
        store_id = StoreId.parse(query.store_id)

        # 所属法人の検証を含めて店舗を取得（存在しない/所属違いは 404 例外）
        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )

        return StoreDto.from_entity(store)
