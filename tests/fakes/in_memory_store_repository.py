from __future__ import annotations

import copy

from app.domain.corporate import CorporateId
from app.domain.store import (
    InsurancePharmacyNumber,
    InsurancePharmacyNumberAlreadyExistsError,
    Store,
    StoreCatalogRepository,
    StoreCode,
    StoreCodeAlreadyExistsError,
    StoreId,
    StoreName,
    StoreNameAlreadyExistsError,
    StoreRepository,
)


class InMemoryStoreRepository(StoreRepository, StoreCatalogRepository):
    """テスト用のインメモリ店舗リポジトリ。

    ``save()`` で一意性違反を送出するのは、本番の永続化層が持つ一意制約を模すため。
    ユースケース側の事前チェックを外しても検知できる状態にしておく。
    """

    def __init__(self) -> None:
        self.items: dict[StoreId, Store] = {}
        #: ``save()`` が呼ばれた回数。変更が無いときに保存を省いているかの検証に使う。
        self.save_count = 0

    async def get(self, store_id: StoreId) -> Store | None:
        item = self.items.get(store_id)
        if item is None:
            return None
        return copy.deepcopy(item)

    async def save(self, store: Store) -> None:
        self.save_count += 1

        if await self.exists_by_name(
            corporate_id=store.corporate_id,
            name=store.names.name,
            excluding_id=store.id,
        ):
            raise StoreNameAlreadyExistsError(
                f"同一法人内に店舗名 '{store.names.name.value}' は既に登録されています。"
            )

        if store.code is not None and await self.exists_by_code(
            corporate_id=store.corporate_id,
            code=store.code,
            excluding_id=store.id,
        ):
            raise StoreCodeAlreadyExistsError(
                f"同一法人内に店舗コード '{store.code.value}' は既に登録されています。"
            )

        if (
            store.insurance_pharmacy_number is not None
            and await self.exists_by_insurance_pharmacy_number(
                number=store.insurance_pharmacy_number,
                excluding_id=store.id,
            )
        ):
            raise InsurancePharmacyNumberAlreadyExistsError(
                f"保険薬局指定番号 '{store.insurance_pharmacy_number.value}' は既に別の店舗で登録されています。"
            )

        self.items[store.id] = copy.deepcopy(store)

    async def exists_by_name(
        self,
        *,
        corporate_id: CorporateId,
        name: StoreName,
        excluding_id: StoreId | None = None,
    ) -> bool:
        return any(
            item.corporate_id == corporate_id
            and item.names.name == name
            and item.id != excluding_id
            for item in self.items.values()
        )

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StoreCode,
        excluding_id: StoreId | None = None,
    ) -> bool:
        return any(
            item.corporate_id == corporate_id
            and item.code == code
            and item.id != excluding_id
            for item in self.items.values()
        )

    async def exists_by_insurance_pharmacy_number(
        self,
        *,
        number: InsurancePharmacyNumber,
        excluding_id: StoreId | None = None,
    ) -> bool:
        return any(
            item.insurance_pharmacy_number == number and item.id != excluding_id
            for item in self.items.values()
        )

    async def list_by_corporate_id(self, corporate_id: CorporateId) -> list[Store]:
        return [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id
        ]

    async def list_all(self) -> list[Store]:
        return [copy.deepcopy(item) for item in self.items.values()]
