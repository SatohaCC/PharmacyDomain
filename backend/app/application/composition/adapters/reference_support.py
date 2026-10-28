"""Applicationのreference_supportを定義する。"""

from __future__ import annotations

from app.domain.corporate.identifiers import CorporateId
from app.domain.store.entities import Store
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


async def load_store_in_corporate(
    repository: StoreRepository, *, corporate_id: CorporateId, store_id: StoreId
) -> Store | None:
    """指定法人の店舗だけを返し、別法人の店舗は ``None`` へ畳む。

    「存在しない」と「別法人」を戻り値で区別しない。区別できる形にすると、
    呼び出し側が別々の例外へ分けられてしまい、他テナントの店舗IDの存在が漏れる。

    店舗の有効・無効は見ない。参照Boundaryの契約が確認するのは存在と法人境界
    だけであり、廃止済み店舗を拒否するかは各コンテキストの業務判断である
    （現時点でそれを要求する契約はない）。
    """
    store = await repository.get(store_id)
    if store is None or store.corporate_id != corporate_id:
        return None
    return store
