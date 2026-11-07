"""薬歴ブロック（動的区分方式）のHTTPルートテスト。"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.application.composition.registry import MedicationHistoryUseCases
from app.application.medication_history.commands.save_medication_history_blocks import (
    SaveMedicationHistoryBlocksUseCase,
)
from app.application.medication_history.queries.list_medication_history_blocks import (
    ListMedicationHistoryBlocksUseCase,
)
from app.bootstrap import create_app
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryCategoryCatalog
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.medication_history_list_blocks import (
    ListMedicationHistoryBlocksProjection,
)
from app.presentational.dependencies import get_medication_history_use_cases
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
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.presentational.helpers import vendor_admin

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture
def client_env() -> Iterator[
    tuple[
        TestClient,
        CorporateId,
        StoreId,
        InMemoryMedicationHistoryRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
    ]
]:
    corporate_repo = AutoProvisioningCorporateRepository()
    corporate_access = create_vendor_corporate_access_for(corporate_repo)
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()

    record_repo = InMemoryMedicationHistoryRepository()
    catalog_repo = InMemoryMedicationHistoryCategoryCatalogRepository()
    store_operations = FakeMedicationHistoryStoreOperations()
    clock = FakeClock()

    projection = ListMedicationHistoryBlocksProjection(
        repository=record_repo,
        catalog_repository=catalog_repo,
    )
    save_blocks_uc = SaveMedicationHistoryBlocksUseCase(
        repository=record_repo,
        catalog_repository=catalog_repo,
        corporate_access=corporate_access,
        store_operations=store_operations,
        clock=clock,
    )
    list_blocks_uc = ListMedicationHistoryBlocksUseCase(
        reader=projection,
        corporate_access=corporate_access,
        store_operations=store_operations,
    )

    medication_history_bundle = MedicationHistoryUseCases(
        start=cast(Any, None),
        update_draft=cast(Any, None),
        finalize=cast(Any, None),
        amend=cast(Any, None),
        correct_fact=cast(Any, None),
        get=cast(Any, None),
        get_follow_up_source=cast(Any, None),
        list_by_patient=cast(Any, None),
        get_medical_profile=cast(Any, None),
        rebuild_medical_profile=cast(Any, None),
        verify_statutory_record=cast(Any, None),
        get_category_catalog=cast(Any, None),
        update_category_catalog=cast(Any, None),
        list_store_current_record_fields=cast(Any, None),
        save_store_current_record_fields=cast(Any, None),
        save_blocks=save_blocks_uc,
        list_blocks=list_blocks_uc,
        record_tracing_report=cast(Any, None),
        record_tracing_report_response=cast(Any, None),
        get_view=cast(Any, None),
        list_external_corrections=cast(Any, None),
        review_external_correction=cast(Any, None),
    )

    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides[get_medication_history_use_cases] = lambda: (
        medication_history_bundle
    )

    test_client = TestClient(app, raise_server_exceptions=True)
    yield test_client, corporate_id, store_id, record_repo, catalog_repo


def test_薬歴ブロック保存および一覧取得_正常系(
    client_env: tuple[
        TestClient,
        CorporateId,
        StoreId,
        InMemoryMedicationHistoryRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
    ],
) -> None:
    # Arrange
    client, corporate_id, store_id, record_repo, catalog_repo = client_env
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corporate_id)
    catalog_repo.items[corporate_id] = catalog

    record = create_record(corporate_id=corporate_id, store_id=store_id)
    record_repo.items[record.id] = record

    base_url = f"/corporates/{corporate_id.value}/medication-histories/{record.id.value}/blocks"

    # Act 1: PUT blocks
    put_res = client.put(
        base_url,
        headers=_HEADERS,
        json={
            "store_id": str(store_id.value),
            "blocks": [
                {
                    "category_code": "s",
                    "content": "花粉症の症状が重いとの訴え。",
                    "display_order": 10,
                    "source_module": "soap",
                },
                {
                    "category_code": "p",
                    "content": "点鼻薬の用法遵守を指導。",
                    "display_order": 20,
                    "source_module": "soap",
                },
            ],
        },
    )

    # Assert 1
    assert put_res.status_code == HTTPStatus.OK
    saved_blocks = put_res.json()
    assert len(saved_blocks) == 2
    assert saved_blocks[0]["category_code"] == "s"
    assert saved_blocks[0]["content"] == "花粉症の症状が重いとの訴え。"
    assert saved_blocks[0]["category_name"] == "S（主観的情報）"
    assert saved_blocks[1]["category_code"] == "p"

    # Act 2: GET blocks
    get_res = client.get(
        base_url,
        params={"store_id": str(store_id.value)},
        headers=_HEADERS,
    )

    # Assert 2
    assert get_res.status_code == HTTPStatus.OK
    listed_blocks = get_res.json()
    assert len(listed_blocks) == 2
    assert listed_blocks[0]["content"] == "花粉症の症状が重いとの訴え。"


def test_受付経由ブロック保存および一覧取得_正常系(
    client_env: tuple[
        TestClient,
        CorporateId,
        StoreId,
        InMemoryMedicationHistoryRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
    ],
) -> None:
    # Arrange
    client, corporate_id, store_id, record_repo, catalog_repo = client_env
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corporate_id)
    catalog_repo.items[corporate_id] = catalog

    record = create_record(corporate_id=corporate_id, store_id=store_id)
    record_repo.items[record.id] = record

    base_url = (
        f"/corporates/{corporate_id.value}/receptions/{record.event_id.value}/blocks"
    )

    # Act 1: PUT reception blocks
    put_res = client.put(
        base_url,
        headers=_HEADERS,
        json={
            "store_id": str(store_id.value),
            "blocks": [
                {
                    "category_code": "s",
                    "content": "受付経由での訴え記録。",
                    "display_order": 10,
                }
            ],
        },
    )

    # Assert 1
    assert put_res.status_code == HTTPStatus.OK
    saved_blocks = put_res.json()
    assert len(saved_blocks) == 1
    assert saved_blocks[0]["content"] == "受付経由での訴え記録。"

    # Act 2: GET reception blocks
    get_res = client.get(
        base_url,
        params={"store_id": str(store_id.value)},
        headers=_HEADERS,
    )

    # Assert 2
    assert get_res.status_code == HTTPStatus.OK
    listed_blocks = get_res.json()
    assert len(listed_blocks) == 1
    assert listed_blocks[0]["content"] == "受付経由での訴え記録。"
