"""店舗ユースケーステストで共有する Arrange 用ヘルパー。"""

from __future__ import annotations

from app.domain.corporate import CorporateId
from app.domain.store import Store
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def save_store(
    repository: InMemoryStoreRepository,
    *,
    corporate_id: CorporateId,
    name: str = "サンプル薬局",
    kana: str = "サンプルヤッキョク",
    code: str | None = None,
    insurance_pharmacy_number: str | None = None,
) -> Store:
    """既定値の店舗をリポジトリへ保存し、保存した集約を返す。"""
    store = create_store(
        corporate_id=corporate_id,
        name=name,
        kana=kana,
        code=code,
        insurance_pharmacy_number=insurance_pharmacy_number,
    )
    await repository.save(store)
    return store
