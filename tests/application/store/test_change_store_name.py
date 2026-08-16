"""店舗名変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.store import ChangeStoreNamesCommand, ChangeStoreNamesUseCase
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate import CorporateId
from app.domain.store import (
    StoreNameAlreadyExistsError,
    StoreNameUniquenessService,
)
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


def create_use_case(repository: InMemoryStoreRepository) -> ChangeStoreNamesUseCase:
    return ChangeStoreNamesUseCase(
        repository,
        StoreNameUniquenessService(repository),
        create_vendor_corporate_access(),
    )


async def test_change_store_names_updates_and_persists_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = create_use_case(repository)

    # Act
    await use_case.execute(
        ChangeStoreNamesCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_name="変更後薬局",
            new_name_kana="ヘンコウゴヤッキョク",
            new_romaji="Henkougo Pharmacy",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.names.name.value == "変更後薬局"
    assert actual.names.kana.value == "ヘンコウゴヤッキョク"
    assert actual.names.romaji is not None
    assert actual.names.romaji.value == "Henkougo Pharmacy"


async def test_change_store_names_allows_updating_kana_only() -> None:
    # Arrange: 正式名称が変わらない場合、重複チェックで自分自身に弾かれてはならない
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id, name="サンプル薬局")
    use_case = create_use_case(repository)

    # Act
    await use_case.execute(
        ChangeStoreNamesCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            new_name="サンプル薬局",
            new_name_kana="サンプルヤッキョクテン",
        )
    )

    # Assert
    actual = await repository.get(store.id)
    assert actual is not None
    assert actual.names.kana.value == "サンプルヤッキョクテン"


async def test_change_store_names_rejects_another_store_name_in_same_corporate() -> (
    None
):
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    target = await save_store(
        repository, corporate_id=corporate_id, name="サンプル薬局"
    )
    await save_store(repository, corporate_id=corporate_id, name="別の薬局")
    use_case = create_use_case(repository)

    # Act
    with pytest.raises(StoreNameAlreadyExistsError):
        await use_case.execute(
            ChangeStoreNamesCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(target.id.value),
                new_name="別の薬局",
                new_name_kana="ベツノヤッキョク",
            )
        )

    # Assert: 変更が保存されていないこと
    actual = await repository.get(target.id)
    assert actual is not None
    assert actual.names.name.value == "サンプル薬局"


async def test_change_store_names_rejects_store_of_another_corporate() -> None:
    # Arrange: 他法人の店舗はテナント境界の外なので未検出として扱う
    repository = InMemoryStoreRepository()
    owner_corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=owner_corporate_id)
    use_case = create_use_case(repository)

    # Act / Assert
    with pytest.raises(StoreNotFoundError):
        await use_case.execute(
            ChangeStoreNamesCommand(
                corporate_id=str(CorporateId.generate().value),
                store_id=str(store.id.value),
                new_name="変更後薬局",
                new_name_kana="ヘンコウゴヤッキョク",
            )
        )
