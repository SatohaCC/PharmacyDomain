"""店舗一覧取得ユースケースのテスト。"""

from __future__ import annotations

from app.application.store import ListStoresQuery, ListStoresUseCase
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_list_stores_returns_summaries_of_the_requesting_corporate() -> None:
    # Arrange: 要求元法人に2件、別法人に1件を用意する
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await save_store(
        repository, corporate_id=corporate_id, name="サンプル薬局", code="ST-001"
    )
    await save_store(repository, corporate_id=corporate_id, name="第二薬局")
    await save_store(repository, corporate_id=CorporateId.generate(), name="他法人薬局")
    use_case = ListStoresUseCase(repository, create_vendor_corporate_access())

    # Act
    actual = await use_case.execute(
        ListStoresQuery(corporate_id=str(corporate_id.value))
    )

    # Assert: 他法人の店舗が混ざらないこと
    assert len(actual) == 2
    assert {summary.name for summary in actual} == {"サンプル薬局", "第二薬局"}
    assert all(summary.corporate_id == str(corporate_id.value) for summary in actual)
    assert {summary.code for summary in actual} == {"ST-001", None}


async def test_list_stores_returns_empty_list_when_corporate_has_no_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    await save_store(repository, corporate_id=CorporateId.generate())
    use_case = ListStoresUseCase(repository, create_vendor_corporate_access())

    # Act
    actual = await use_case.execute(
        ListStoresQuery(corporate_id=str(CorporateId.generate().value))
    )

    # Assert
    assert actual == []
