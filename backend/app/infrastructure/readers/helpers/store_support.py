"""Applicationのstore_supportを定義する。"""

from __future__ import annotations

from app.application.store.errors import StoreNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.entities import Store
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


async def load_store_or_raise(
    repository: StoreRepository, *, corporate_id: CorporateId, store_id: StoreId
) -> Store:
    """指定された法人に所属する店舗を取得し、存在しないまたは別法人の場合は例外を送出する。

    Args:
        repository: 店舗リポジトリ
        corporate_id: 要求元の法人ID
        store_id: 取得対象の店舗ID

    Returns:
        Store: 取得された店舗集約

    Raises:
        StoreNotFoundError: 店舗が存在しない、または別法人に所属している場合
    """
    store = await repository.get(store_id)
    if store is None or store.corporate_id != corporate_id:
        raise StoreNotFoundError(
            f"指定された店舗（ID: {store_id.value}）が見つかりません。"
        )
    return store
