"""Yakureki仕様に準拠したNSIPS HTTPルートの振る舞いテスト。"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.application.composition.registry import IntegrationUseCases
from app.application.integration.queries.get_nsips_source import GetNsipsSourceUseCase
from app.bootstrap import create_app
from app.infrastructure.readers.integration_nsips_source import (
    PostgresGetNsipsSourceQueryReader,
)
from app.presentational.dependencies import get_integration_use_cases
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.integration.nsips.helpers import NsipsFixture, create_fixture
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.presentational.helpers import vendor_admin

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture
async def nsips_fixture() -> NsipsFixture:
    return await create_fixture()


@pytest.fixture
def client(nsips_fixture: NsipsFixture) -> Iterator[TestClient]:
    reader = PostgresGetNsipsSourceQueryReader(
        reception_repository=nsips_fixture.reception_repo,
        medication_history_repository=nsips_fixture.medication_history_repo,
    )
    get_nsips_source = GetNsipsSourceUseCase(
        reader=reader,
        corporate_access=create_vendor_corporate_access_for(
            nsips_fixture.corporate_repo
        ),
    )
    bundle = IntegrationUseCases(
        ingest_nsips=nsips_fixture.use_case,
        get_nsips_source=get_nsips_source,
    )
    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides[get_integration_use_cases] = lambda: bundle
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _valid_bundle(days_supply: int = 14) -> dict[str, Any]:
    return {
        "header_version": "yakureki-http",
        "patient": {
            "external_patient_id": "P-HTTP-YAKUREKI",
            "kanji_name": "山田 太郎",
            "kana_name": "ヤマダ タロウ",
            "birth_date": "1990-01-01",
            "gender": "1",
            "postal_code": "100-0001",
            "address": "東京都千代田区1-1-1",
            "phone_number": "03-1111-2222",
        },
        "prescription": {
            "document_number": "DOC-HTTP-001",
            "issued_date": "2026-06-22",
            "institution_code": "1310001",
            "institution_name": "千代田クリニック",
            "department_code": "01",
            "department_name": "内科",
            "doctor_name": "佐藤 一郎",
            "expiration_date": "2026-06-26",
            "remaining_medication_check_code": "1",
            "refill_total_uses": 3,
            "remarks": [
                {
                    "sequence_number": 1,
                    "remark_type_code": "01",
                    "text": "一包化希望",
                }
            ],
            "rps": [
                {
                    "rp_number": 1,
                    "group_name": "内服",
                    "instructions": "1日3回毎食後",
                    "dispensing_quantity": days_supply,
                    "dosage_form_code": "1",
                    "dosage_form_name": "内服錠",
                    "usage_code": "101",
                    "daily_frequency": 3,
                    "usage_supplements": [
                        {
                            "category_code": "01",
                            "text": "粉砕不可",
                        }
                    ],
                    "medicines": [
                        {
                            "medicine_code": "610406001",
                            "medicine_name": "ロキソニン錠60mg",
                            "dosage": "1",
                            "unit": "錠",
                            "days_supply": days_supply,
                            "yj_code": "1149019F1030",
                            "info_category": "drug",
                            "supplements": [
                                {
                                    "category_code": "01",
                                    "text": "後発品変更不可",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        "insurance": {
            "insurer_number": "123456",
            "insured_symbol": "12",
            "insured_number": "345678",
        },
    }


def test_POST_nsips_ファイル名指定_受付ID省略で201Createdと台帳情報が返る(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """A_<file_id>.xml を指定してPOSTすると受付IDが自動発行され、201 Created と台帳情報が返る。"""
    corporate_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    url = f"/corporates/{corporate_id}/stores/{store_id}/integrations/nsips"

    payload = {
        "file_name": "A_20260622-0001.xml",
        "structured_bundle": _valid_bundle(14),
    }

    response = client.post(url, json=payload, headers=_HEADERS)
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["file_id"] == "20260622-0001"
    assert data["operation"] == "create"
    assert data["status"] == "applied"
    assert data["was_already_applied"] is False
    assert data["reception_id"] is not None


def test_POST_nsips_同一ファイル再送で200OKとalready_appliedが返る(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """同一内容のファイルを再送すると、200 OK と was_already_applied=True が返る。"""
    corporate_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    url = f"/corporates/{corporate_id}/stores/{store_id}/integrations/nsips"

    payload = {
        "file_name": "A_20260622-0002.xml",
        "structured_bundle": _valid_bundle(14),
    }

    initial = client.post(url, json=payload, headers=_HEADERS)
    assert initial.status_code == HTTPStatus.CREATED

    duplicate = client.post(url, json=payload, headers=_HEADERS)
    assert duplicate.status_code == HTTPStatus.OK
    data = duplicate.json()
    assert data["was_already_applied"] is True
    assert data["reception_id"] == initial.json()["reception_id"]


def test_POST_nsips_訂正ファイル_U指定で同一受付に訂正が適用される(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """登録後に U_<file_id>.xml をPOSTすると、同一受付に訂正が適用される。"""
    corporate_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    url = f"/corporates/{corporate_id}/stores/{store_id}/integrations/nsips"

    create_payload = {
        "file_name": "A_20260622-0003.xml",
        "structured_bundle": _valid_bundle(14),
    }
    created = client.post(url, json=create_payload, headers=_HEADERS)
    assert created.status_code == HTTPStatus.CREATED
    reception_id = created.json()["reception_id"]

    update_payload = {
        "file_name": "U_20260622-0003.xml",
        "structured_bundle": _valid_bundle(28),
    }
    updated = client.post(url, json=update_payload, headers=_HEADERS)
    assert updated.status_code == HTTPStatus.CREATED
    data = updated.json()
    assert data["operation"] == "update"
    assert data["reception_id"] == reception_id


def test_POST_nsips_取消ファイル_本文なしで201Createdと取消が適用される(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """D_<file_id>.xml を本文なしでPOSTすると、対象受付が WITHDRAWN に取り消される。"""
    corporate_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    url = f"/corporates/{corporate_id}/stores/{store_id}/integrations/nsips"

    create_payload = {
        "file_name": "A_20260622-0004.xml",
        "structured_bundle": _valid_bundle(14),
    }
    created = client.post(url, json=create_payload, headers=_HEADERS)
    assert created.status_code == HTTPStatus.CREATED

    delete_payload = {
        "file_name": "D_20260622-0004.xml",
    }
    deleted = client.post(url, json=delete_payload, headers=_HEADERS)
    assert deleted.status_code == HTTPStatus.CREATED
    data = deleted.json()
    assert data["operation"] == "delete"
    assert data["source_status"] == "withdrawn"
