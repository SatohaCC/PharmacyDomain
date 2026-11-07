"""店舗今回記載欄設定ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.medication_history.commands.models import CurrentRecordFieldInput
from app.application.medication_history.commands.save_store_current_record_fields import (
    SaveStoreCurrentRecordFieldsCommand,
    SaveStoreCurrentRecordFieldsUseCase,
)
from app.application.medication_history.queries.list_store_current_record_fields import (
    ListStoreCurrentRecordFieldsQuery,
    ListStoreCurrentRecordFieldsUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.medication_history.identifiers import CurrentRecordFieldId
from app.domain.medication_history.primitives import (
    CategoryDisplayOrder,
    CurrentRecordFieldLabel,
    MediumCategoryCode,
)
from app.domain.medication_history.value_objects import CurrentRecordFieldDefinition
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.medication_history_list_store_current_record_fields import (
    ListStoreCurrentRecordFieldsProjection,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.fakes.fake_medication_history_store_operations import (
    FakeMedicationHistoryStoreOperations,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
)


@pytest.fixture
def corporate_repo() -> AutoProvisioningCorporateRepository:
    return AutoProvisioningCorporateRepository()


@pytest.fixture
def catalog_repo() -> InMemoryMedicationHistoryCategoryCatalogRepository:
    return InMemoryMedicationHistoryCategoryCatalogRepository()


@pytest.fixture
def store_operations() -> FakeMedicationHistoryStoreOperations:
    return FakeMedicationHistoryStoreOperations()


async def test_店舗今回記載欄一覧_法人共通と自店舗項目を返し他店舗項目は除外する(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
) -> None:
    """法人共通項目と対象店舗項目が返され、他店舗の項目は除外されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    corp_id = CorporateId.generate()
    store_a = StoreId.generate()
    store_b = StoreId.generate()

    # デフォルトカタログに項目を追加
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corp_id)
    common_field = CurrentRecordFieldDefinition(
        field_id=CurrentRecordFieldId.generate(),
        label=CurrentRecordFieldLabel("法人共通確認事項"),
        display_order=CategoryDisplayOrder(1),
        store_id=None,
        category_code=MediumCategoryCode("residual_drug"),
    )
    store_a_field = CurrentRecordFieldDefinition(
        field_id=CurrentRecordFieldId.generate(),
        label=CurrentRecordFieldLabel("店舗A特有ヒアリング"),
        display_order=CategoryDisplayOrder(2),
        store_id=store_a,
    )
    store_b_field = CurrentRecordFieldDefinition(
        field_id=CurrentRecordFieldId.generate(),
        label=CurrentRecordFieldLabel("店舗B特有ヒアリング"),
        display_order=CategoryDisplayOrder(3),
        store_id=store_b,
    )
    catalog = catalog.update_current_record_fields(
        (common_field, store_a_field, store_b_field)
    )
    await catalog_repo.save(catalog)

    query_use_case = ListStoreCurrentRecordFieldsUseCase(
        reader=ListStoreCurrentRecordFieldsProjection(catalog_repo),
        corporate_access=corp_access,
        store_operations=store_operations,
    )
    results = await query_use_case.execute(
        ListStoreCurrentRecordFieldsQuery(
            corporate_id=str(corp_id.value),
            store_id=str(store_a.value),
        )
    )

    labels = [r.label for r in results]
    assert "法人共通確認事項" in labels
    assert "店舗A特有ヒアリング" in labels
    assert "店舗B特有ヒアリング" not in labels

    # badge_label の解決確認
    common_dto = next(r for r in results if r.label == "法人共通確認事項")
    assert common_dto.category_badge_label == "残薬確認"


async def test_店舗今回記載欄保存_自店舗項目を保存し他店舗および法人共通項目を保持する(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
) -> None:
    """店舗固有の設定保存で、他店舗および法人共通の設定が失われないこと。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    corp_id = CorporateId.generate()
    store_a = StoreId.generate()
    store_b = StoreId.generate()

    # 初期設定: 法人共通項目と店舗B項目をあらかじめ登録
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corp_id)
    common_field = CurrentRecordFieldDefinition(
        field_id=CurrentRecordFieldId.generate(),
        label=CurrentRecordFieldLabel("全店共通ヒアリング"),
        display_order=CategoryDisplayOrder(1),
        store_id=None,
    )
    store_b_field = CurrentRecordFieldDefinition(
        field_id=CurrentRecordFieldId.generate(),
        label=CurrentRecordFieldLabel("店舗B項目"),
        display_order=CategoryDisplayOrder(2),
        store_id=store_b,
    )
    catalog = catalog.update_current_record_fields((common_field, store_b_field))
    await catalog_repo.save(catalog)

    save_use_case = SaveStoreCurrentRecordFieldsUseCase(
        repository=catalog_repo,
        corporate_access=corp_access,
        store_operations=store_operations,
    )
    saved = await save_use_case.execute(
        SaveStoreCurrentRecordFieldsCommand(
            corporate_id=str(corp_id.value),
            store_id=str(store_a.value),
            fields=(
                CurrentRecordFieldInput(
                    label="新規店舗A項目1",
                    display_order=10,
                ),
            ),
        )
    )

    assert len(saved) == 2
    assert any(s.label == "全店共通ヒアリング" for s in saved)
    assert any(
        s.label == "新規店舗A項目1" and s.store_id == str(store_a.value) for s in saved
    )

    # 全店共通項目および店舗B側も残っていることを確認
    updated_catalog = await catalog_repo.get(corporate_id=corp_id)
    assert updated_catalog is not None
    common_fields = [
        f for f in updated_catalog.current_record_fields if f.store_id is None
    ]
    b_fields = [
        f for f in updated_catalog.current_record_fields if f.store_id == store_b
    ]
    assert len(common_fields) == 1
    assert common_fields[0].label.value == "全店共通ヒアリング"
    assert len(b_fields) == 1
    assert b_fields[0].label.value == "店舗B項目"


async def test_店舗今回記載欄_許可されていない店舗の操作_拒否されること(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
    store_operations: FakeMedicationHistoryStoreOperations,
) -> None:
    """操作権限のない他店舗への設定取得および保存が拒否されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    corp_id = CorporateId.generate()
    forbidden_store = StoreId.generate()

    # 対象店舗の操作でエラーを送出するように設定
    store_operations.failures[(corp_id, forbidden_store)] = (
        TenantBoundaryNotFoundError()
    )

    query_use_case = ListStoreCurrentRecordFieldsUseCase(
        reader=ListStoreCurrentRecordFieldsProjection(catalog_repo),
        corporate_access=corp_access,
        store_operations=store_operations,
    )
    with pytest.raises(TenantBoundaryNotFoundError):
        await query_use_case.execute(
            ListStoreCurrentRecordFieldsQuery(
                corporate_id=str(corp_id.value),
                store_id=str(forbidden_store.value),
            )
        )

    save_use_case = SaveStoreCurrentRecordFieldsUseCase(
        repository=catalog_repo,
        corporate_access=corp_access,
        store_operations=store_operations,
    )
    with pytest.raises(TenantBoundaryNotFoundError):
        await save_use_case.execute(
            SaveStoreCurrentRecordFieldsCommand(
                corporate_id=str(corp_id.value),
                store_id=str(forbidden_store.value),
                fields=(),
            )
        )
