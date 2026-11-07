"""今回記載欄および業務EventのHTTPルート統合テスト。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.application.care_event.commands.create_event import CreateEventUseCase
from app.application.care_event.queries.list_store_care_events import (
    ListStoreCareEventsUseCase,
)
from app.application.composition.registry import (
    CareEventUseCases,
    MedicationHistoryUseCases,
    ReceptionUseCases,
)
from app.application.medication_history.commands.ensure_category_catalog import (
    EnsureCategoryCatalogUseCase,
)
from app.application.medication_history.commands.save_store_current_record_fields import (
    SaveStoreCurrentRecordFieldsUseCase,
)
from app.application.medication_history.commands.update_category_catalog import (
    UpdateCategoryCatalogUseCase,
)
from app.application.medication_history.queries.list_store_current_record_fields import (
    ListStoreCurrentRecordFieldsUseCase,
)
from app.application.reception.commands.save_current_record_values import (
    SaveCurrentRecordValuesUseCase,
)
from app.application.reception.queries.get_current_record_values import (
    GetCurrentRecordValuesUseCase,
)
from app.bootstrap import create_app
from app.domain.care_event.entities import EventDefinition
from app.domain.care_event.identifiers import EventTypeId
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import CurrentRecordFieldId
from app.domain.patient.identifiers import PatientId
from app.domain.reception.entities import Reception
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import ReceptionFingerprint
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.care_event_list_store_events import (
    ListStoreCareEventsProjection,
)
from app.infrastructure.readers.medication_history_list_store_current_record_fields import (
    ListStoreCurrentRecordFieldsProjection,
)
from app.infrastructure.readers.reception_get_current_record_values import (
    GetCurrentRecordValuesProjection,
)
from app.presentational.dependencies import (
    get_care_event_use_cases,
    get_medication_history_use_cases,
    get_reception_use_cases,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_event_patient_boundary import FakeEventPatientBoundary
from tests.fakes.fake_medication_history_store_operations import (
    FakeMedicationHistoryStoreOperations,
)
from tests.fakes.in_memory_event_definition_repository import (
    InMemoryEventDefinitionRepository,
)
from tests.fakes.in_memory_event_repository import InMemoryEventRepository
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
)
from tests.fakes.in_memory_reception_repository import InMemoryReceptionRepository
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.presentational.helpers import vendor_admin

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture
def client() -> Iterator[
    tuple[
        TestClient,
        CorporateId,
        StoreId,
        PatientId,
        InMemoryReceptionRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
        InMemoryEventRepository,
    ]
]:
    corporate_repo = AutoProvisioningCorporateRepository()
    corporate_access = create_vendor_corporate_access_for(corporate_repo)
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    patient_id = PatientId.generate()

    # Repositories
    catalog_repo = InMemoryMedicationHistoryCategoryCatalogRepository()
    reception_repo = InMemoryReceptionRepository()
    event_repo = InMemoryEventRepository()
    event_def_repo = InMemoryEventDefinitionRepository()

    # Standard event definitions
    phone_def = EventDefinition(
        id=EventTypeId.generate(),
        name=EventTypeName("電話フォローアップ"),
        standard_code=EventTypeStandardCode("telephone_follow_up"),
    )
    event_def_repo.items[phone_def.id] = phone_def

    patient_boundary = FakeEventPatientBoundary()
    patient_boundary.register(corporate_id=corporate_id, patient_id=patient_id)
    store_operations = FakeMedicationHistoryStoreOperations()
    clock = FakeClock()

    # CareEvent use cases
    care_event_bundle = CareEventUseCases(
        create=CreateEventUseCase(
            event_repository=event_repo,
            event_definition_repository=event_def_repo,
            patient_boundary=patient_boundary,
            corporate_access=corporate_access,
            store_operations=store_operations,
            clock=clock,
        ),
        get=cast(Any, None),
        create_definition=cast(Any, None),
        list_definitions=cast(Any, None),
        update_definition=cast(Any, None),
        list_related_candidates=cast(Any, None),
        list_by_store=ListStoreCareEventsUseCase(
            reader=ListStoreCareEventsProjection(event_repo),
            corporate_access=corporate_access,
            store_operations=store_operations,
        ),
    )

    # Reception use cases
    reception_bundle = ReceptionUseCases(
        associate_medication_history=cast(Any, None),
        save_current_record_values=SaveCurrentRecordValuesUseCase(
            reception_repository=reception_repo,
            corporate_access=corporate_access,
        ),
        get_current_record_values=GetCurrentRecordValuesUseCase(
            reader=GetCurrentRecordValuesProjection(reception_repo),
            corporate_access=corporate_access,
        ),
    )

    # MedicationHistory use cases
    med_history_bundle = MedicationHistoryUseCases(
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
        get_category_catalog=EnsureCategoryCatalogUseCase(
            catalog_repo, corporate_access
        ),
        update_category_catalog=UpdateCategoryCatalogUseCase(
            catalog_repo, corporate_access
        ),
        list_store_current_record_fields=ListStoreCurrentRecordFieldsUseCase(
            reader=ListStoreCurrentRecordFieldsProjection(catalog_repo),
            corporate_access=corporate_access,
        ),
        save_store_current_record_fields=SaveStoreCurrentRecordFieldsUseCase(
            repository=catalog_repo,
            corporate_access=corporate_access,
        ),
        record_tracing_report=cast(Any, None),
        record_tracing_report_response=cast(Any, None),
        get_view=cast(Any, None),
        list_external_corrections=cast(Any, None),
        review_external_correction=cast(Any, None),
    )

    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides[get_care_event_use_cases] = lambda: care_event_bundle
    app.dependency_overrides[get_reception_use_cases] = lambda: reception_bundle
    app.dependency_overrides[get_medication_history_use_cases] = lambda: (
        med_history_bundle
    )

    test_client = TestClient(app, raise_server_exceptions=True)
    yield (
        test_client,
        corporate_id,
        store_id,
        patient_id,
        reception_repo,
        catalog_repo,
        event_repo,
    )
    app.dependency_overrides.clear()


def test_store_current_record_fields_crud_routes(
    client: tuple[
        TestClient,
        CorporateId,
        StoreId,
        PatientId,
        InMemoryReceptionRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
        InMemoryEventRepository,
    ],
) -> None:
    """店舗今回記載欄定義の取得・更新ルートのテスト。"""
    c, corp_id, store_id, _, _, _, _ = client
    cid = str(corp_id.value)
    sid = str(store_id.value)

    # 初期取得（デフォルト項目が返る）
    res = c.get(
        f"/corporates/{cid}/stores/{sid}/current-record-fields", headers=_HEADERS
    )
    assert res.status_code == HTTPStatus.OK
    initial_fields = res.json()
    assert isinstance(initial_fields, list)

    # 店舗固有の項目を更新
    payload = {
        "fields": [
            {
                "label": "今回体調ヒアリング",
                "display_order": 1,
                "category_code": "residual_drug",
                "is_archived": False,
            }
        ]
    }
    put_res = c.put(
        f"/corporates/{cid}/stores/{sid}/current-record-fields",
        json=payload,
        headers=_HEADERS,
    )
    assert put_res.status_code == HTTPStatus.OK
    updated_fields = put_res.json()
    assert any(f["label"] == "今回体調ヒアリング" for f in updated_fields)


def test_reception_current_record_values_routes(
    client: tuple[
        TestClient,
        CorporateId,
        StoreId,
        PatientId,
        InMemoryReceptionRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
        InMemoryEventRepository,
    ],
) -> None:
    """受付の今回記載欄入力値の取得・保存ルートのテスト。"""
    c, corp_id, store_id, pat_id, reception_repo, _, _ = client
    cid = str(corp_id.value)
    sid = str(store_id.value)

    # 受付を作成して保存
    reception = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp_id,
        store_id=store_id,
        patient_id=pat_id,
        latest_fingerprint=ReceptionFingerprint("0" * 64),
        field_fingerprints=(),
    )
    reception_repo.items[(corp_id, store_id, reception.id)] = reception
    rid = str(reception.id.value)
    fid = str(CurrentRecordFieldId.generate().value)

    # 入力値を保存
    payload = {
        "store_id": sid,
        "values": [
            {
                "field_id": fid,
                "value_text": "残薬なし。体調変化特になし。",
            }
        ],
    }
    put_res = c.put(
        f"/corporates/{cid}/receptions/{rid}/current-record-fields",
        json=payload,
        headers=_HEADERS,
    )
    assert put_res.status_code == HTTPStatus.OK
    saved = put_res.json()
    assert len(saved) == 1
    assert saved[0]["field_id"] == fid
    assert saved[0]["value_text"] == "残薬なし。体調変化特になし。"

    # 取得
    get_res = c.get(
        f"/corporates/{cid}/receptions/{rid}/current-record-fields",
        params={"store_id": sid},
        headers=_HEADERS,
    )
    assert get_res.status_code == HTTPStatus.OK
    fetched = get_res.json()
    assert len(fetched) == 1
    assert fetched[0]["value_text"] == "残薬なし。体調変化特になし。"


def test_care_event_store_listing_and_quick_creation_routes(
    client: tuple[
        TestClient,
        CorporateId,
        StoreId,
        PatientId,
        InMemoryReceptionRepository,
        InMemoryMedicationHistoryCategoryCatalogRepository,
        InMemoryEventRepository,
    ],
) -> None:
    """店舗の業務Event一覧と標準コード起票ルートのテスト。"""
    c, corp_id, store_id, pat_id, _, _, _ = client
    cid = str(corp_id.value)
    sid = str(store_id.value)
    pid = str(pat_id.value)

    # standard_code "phone" で起票
    create_payload = {
        "store_id": sid,
        "patient_id": pid,
        "standard_code": "phone",
        "occurred_at": datetime(2026, 11, 7, 10, 30, tzinfo=UTC).isoformat(),
    }
    post_res = c.post(
        f"/corporates/{cid}/events",
        json=create_payload,
        headers=_HEADERS,
    )
    assert post_res.status_code == HTTPStatus.CREATED
    created_event = post_res.json()
    assert created_event["event_type_name"] == "電話フォローアップ"

    # 店舗のEvent一覧を取得
    list_res = c.get(
        f"/corporates/{cid}/stores/{sid}/care-events",
        headers=_HEADERS,
    )
    assert list_res.status_code == HTTPStatus.OK
    events = list_res.json()
    assert len(events) == 1
    assert events[0]["event_id"] == created_event["event_id"]
