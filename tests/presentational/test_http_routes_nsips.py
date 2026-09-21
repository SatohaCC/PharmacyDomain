"""NSIPS取込HTTPルートの振る舞いテスト (TC-26〜TC-30)。"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.di.bundles.integration import IntegrationUseCases
from app.presentational import create_app
from app.presentational.dependencies import get_integration_use_cases
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
    bundle = IntegrationUseCases(ingest_nsips=nsips_fixture.use_case)
    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides[get_integration_use_cases] = lambda: bundle
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_生テキストNSIPSのPOSTが201を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-26: 生NSIPSテキストをPOSTすると201 Createdが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "operator_staff_id": str(nsips_fixture.pharmacist_id.value),
        "raw_nsips_text": "1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["is_new_patient"] is True
    assert data["prescription_id"] is not None
    assert data["dispensing_id"] is not None
    assert data["medication_history_id"] is not None


def test_構造化JSONペイロードのPOSTが201を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-27: 構造化JSONペイロードをPOSTすると201 Createdが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "operator_staff_id": str(nsips_fixture.pharmacist_id.value),
        "structured_bundle": {
            "header_version": "1.0",
            "patient": {
                "external_patient_id": "P-1001",
                "kanji_name": "山田太郎",
                "kana_name": "ヤマダタロウ",
                "birth_date": "1980-01-01",
                "gender": "male",
            },
            "prescription": {
                "document_number": "DOC-001",
                "issued_date": "2026-09-21",
                "institution_code": "1310001",
                "institution_name": "中央診療所",
                "department_code": "01",
                "department_name": "内科",
                "doctor_name": "佐藤医師",
                "rps": [],
            },
        },
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["patient_name"] == "山田太郎"
    assert data["is_follow_up_only"] is True


def test_重複処方の再送が200_OKを返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-28: 同一処方箋番号を再送すると200 OKが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "operator_staff_id": str(nsips_fixture.pharmacist_id.value),
        "raw_nsips_text": "1,20260921,DOC-DUP,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    }
    res1 = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert res1.status_code == HTTPStatus.CREATED

    res2 = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert res2.status_code == HTTPStatus.OK
    assert res2.json()["is_duplicate"] is True


def test_構文不正テキストのPOSTが422を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-29: 構文不正（必須項目不足など）のテキストをPOSTすると422が返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "operator_staff_id": str(nsips_fixture.pharmacist_id.value),
        "raw_nsips_text": "INVALID SYNTAX TEXT",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_未認証のPOSTが401を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-30: 認証ヘッダなしでPOSTすると401 Unauthorizedが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "operator_staff_id": str(nsips_fixture.pharmacist_id.value),
        "raw_nsips_text": "1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
