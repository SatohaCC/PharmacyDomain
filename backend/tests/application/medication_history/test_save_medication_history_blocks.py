"""薬歴ブロック保存・一覧ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.common.exceptions import NotFoundError
from app.application.medication_history.commands.models import (
    MedicationHistoryBlockInput,
)
from app.application.medication_history.commands.save_medication_history_blocks import (
    SaveMedicationHistoryBlocksCommand,
    SaveMedicationHistoryBlocksUseCase,
)
from app.application.medication_history.queries.list_medication_history_blocks import (
    ListMedicationHistoryBlocksUseCase,
)
from app.application.medication_history.queries.models import (
    ListMedicationHistoryBlocksQuery,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.medication_history_list_blocks import (
    ListMedicationHistoryBlocksProjection,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.factories.medication_history_factory import create_record
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_medication_history_store_operations import (
    FakeMedicationHistoryStoreOperations,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
    InMemoryMedicationHistoryRepository,
)


@pytest.fixture
def corporate_repo() -> AutoProvisioningCorporateRepository:
    return AutoProvisioningCorporateRepository()


@pytest.fixture
def record_repo() -> InMemoryMedicationHistoryRepository:
    return InMemoryMedicationHistoryRepository()


@pytest.fixture
def catalog_repo() -> InMemoryMedicationHistoryCategoryCatalogRepository:
    return InMemoryMedicationHistoryCategoryCatalogRepository()


@pytest.fixture
def store_operations() -> FakeMedicationHistoryStoreOperations:
    return FakeMedicationHistoryStoreOperations()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


async def test_薬歴ブロック保存_正常系_ブロックが保存されDtoが返される(
    record_repo: InMemoryMedicationHistoryRepository,
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
    clock: FakeClock,
) -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    corporate_access = create_vendor_corporate_access_for(
        repository=corporate_repo,
    )
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corporate_id)
    await catalog_repo.save(catalog)

    record = create_record(corporate_id=corporate_id, store_id=store_id)
    await record_repo.save(record)

    use_case = SaveMedicationHistoryBlocksUseCase(
        repository=record_repo,
        catalog_repository=catalog_repo,
        corporate_access=corporate_access,
        store_operations=store_operations,
        clock=clock,
    )

    command = SaveMedicationHistoryBlocksCommand(
        corporate_id=str(corporate_id.value),
        store_id=str(store_id.value),
        record_id=str(record.id.value),
        blocks=(
            MedicationHistoryBlockInput(
                category_code="s",
                content="自覚症状なし。",
                display_order=10,
                source_module="soap",
            ),
            MedicationHistoryBlockInput(
                category_code="o",
                content="検査値特記事項なし。",
                display_order=20,
                source_module="soap",
            ),
        ),
    )

    # Act
    dtos = await use_case.execute(command)

    # Assert
    assert len(dtos) == 2
    assert dtos[0].category_code == "s"
    assert dtos[0].content == "自覚症状なし。"
    assert dtos[0].category_name == "S（主観的情報）"
    assert dtos[1].category_code == "o"
    assert dtos[1].content == "検査値特記事項なし。"

    # Verify repository updated
    updated_record = await record_repo.get(
        corporate_id=corporate_id, record_id=record.id
    )
    assert updated_record is not None
    assert len(updated_record.blocks) == 2


async def test_薬歴ブロック保存_存在しない薬歴_NotFoundErrorが発生する(
    record_repo: InMemoryMedicationHistoryRepository,
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
    clock: FakeClock,
) -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    corporate_access = create_vendor_corporate_access_for(
        repository=corporate_repo,
    )

    use_case = SaveMedicationHistoryBlocksUseCase(
        repository=record_repo,
        catalog_repository=catalog_repo,
        corporate_access=corporate_access,
        store_operations=store_operations,
        clock=clock,
    )

    command = SaveMedicationHistoryBlocksCommand(
        corporate_id=str(corporate_id.value),
        store_id=str(store_id.value),
        record_id="0192e26e-4e4b-7013-8869-72dfab779951",
        blocks=(),
    )

    # Act & Assert
    with pytest.raises(NotFoundError):
        await use_case.execute(command)


async def test_薬歴ブロック一覧_正常系_ブロックが取得されカテゴリ名が付与される(
    record_repo: InMemoryMedicationHistoryRepository,
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
    clock: FakeClock,
) -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    corporate_access = create_vendor_corporate_access_for(
        repository=corporate_repo,
    )
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corporate_id)
    await catalog_repo.save(catalog)

    record = create_record(corporate_id=corporate_id, store_id=store_id)
    await record_repo.save(record)

    save_use_case = SaveMedicationHistoryBlocksUseCase(
        repository=record_repo,
        catalog_repository=catalog_repo,
        corporate_access=corporate_access,
        store_operations=store_operations,
        clock=clock,
    )
    await save_use_case.execute(
        SaveMedicationHistoryBlocksCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store_id.value),
            record_id=str(record.id.value),
            blocks=(
                MedicationHistoryBlockInput(
                    category_code="a",
                    content="アドヒアランス良好。",
                    display_order=10,
                ),
            ),
        )
    )

    projection = ListMedicationHistoryBlocksProjection(
        repository=record_repo,
        catalog_repository=catalog_repo,
    )
    list_use_case = ListMedicationHistoryBlocksUseCase(
        reader=projection,
        corporate_access=corporate_access,
        store_operations=store_operations,
    )

    # Act
    results = await list_use_case.execute(
        ListMedicationHistoryBlocksQuery(
            corporate_id=str(corporate_id.value),
            store_id=str(store_id.value),
            record_id=str(record.id.value),
        )
    )

    # Assert
    assert len(results) == 1
    assert results[0].category_code == "a"
    assert results[0].content == "アドヒアランス良好。"
    assert results[0].category_name == "A（評価・判断）"
