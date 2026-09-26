"""NSIPS取込HTTPルートの振る舞いテスト。"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.di.bundles.integration import IntegrationUseCases
from app.presentational.app_factory import create_app
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
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_tc45_未確認版raw形式のPOSTは422で拒否し書込みを行わない(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """対応版・列定義が未確認のraw形式を成功扱いしない。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
        "raw_nsips_text": "1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


def test_構造化JSONペイロードのPOSTが201を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """有効な構造化JSONペイロードをPOSTすると201 Createdが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
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


@pytest.mark.parametrize(
    "invalid_kind",
    ("missing", "malformed", "uuid4"),
    ids=("受付IDなし", "UUID形式不正", "UUIDv4"),
)
def test_tc50_受付IDがないかUUIDv7でなければ書込み前に422(
    client: TestClient,
    nsips_fixture: NsipsFixture,
    invalid_kind: str,
) -> None:
    """受付IDは呼出元が発行したUUIDv7に限り、必須入力として扱う。"""
    payload: dict[str, Any] = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "structured_bundle": _valid_structured_bundle(),
    }
    if invalid_kind == "malformed":
        payload["reception_id"] = "not-a-uuid"
    elif invalid_kind == "uuid4":
        payload["reception_id"] = str(uuid.uuid4())

    response = client.post(
        f"/corporates/{nsips_fixture.corporate_id.value}/stores/{nsips_fixture.store_id.value}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


def test_重複処方の再送が200_OKを返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """同一処方箋番号を再送すると200 OKが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    structured_bundle = _valid_structured_bundle()
    structured_bundle["prescription"]["document_number"] = "DOC-DUP"
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
        "structured_bundle": structured_bundle,
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
    """構文不正な生テキストをPOSTすると422が返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
        "raw_nsips_text": "INVALID SYNTAX TEXT",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


def test_未認証のPOSTが401を返す(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """認証ヘッダなしでPOSTすると401 Unauthorizedが返る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
        "raw_nsips_text": "1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n",
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_tc40_構造化JSONによる保険_調剤日_加算の取込(
    client: TestClient, nsips_fixture: NsipsFixture
) -> None:
    """TC-40: 拡張値を持つ有効な構造化JSONがPOST応答まで通る。"""
    corp_id = str(nsips_fixture.corporate_id.value)
    store_id = str(nsips_fixture.store_id.value)
    payload = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
        "reception_id": str(uuid.uuid7()),
        "structured_bundle": {
            "header_version": "1.0",
            "patient": {
                "external_patient_id": "P-4001",
                "kanji_name": "調剤四郎",
                "kana_name": "チョウザイシロウ",
                "birth_date": "1990-01-01",
                "gender": "1",
            },
            "prescription": {
                "document_number": "DOC-TC41-01",
                "issued_date": "2026-09-20",
                "institution_code": "1310001",
                "institution_name": "中央診療所",
                "doctor_name": "佐藤医師",
                "rps": [
                    {
                        "rp_number": 1,
                        "group_name": "内服",
                        "instructions": "1日3回毎食後",
                        "dispensing_quantity": 14,
                        "medicines": [
                            {
                                "medicine_code": "610406001",
                                "medicine_name": "アムロジピン",
                                "dosage": "1",
                                "unit": "錠",
                            }
                        ],
                    }
                ],
            },
            "dispensed_date": "2026-09-22",
            "insurance": {
                "insurer_number": "138001",
                "insured_symbol": "記号X",
                "insured_number": "番号789",
                "branch_number": "01",
                "insured_type": "self",
                "benefit_ratio": 70,
            },
            "additions": [
                {
                    "code": "140000110",
                    "name": "特定薬剤管理指導加算２",
                    "points": 100,
                    "quantity": 1,
                }
            ],
        },
    }
    response = client.post(
        f"/corporates/{corp_id}/stores/{store_id}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["prescription_id"] is not None
    assert data["dispensing_id"] is not None
    assert data["medication_history_id"] is None
    assert nsips_fixture.medication_history_repo.items == {}
    assert data["coverage_selection_record_id"] is not None
    assert data["dispensed_date"] == "2026-09-22"
    assert "特定薬剤管理指導加算２" in data["addition_names"]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    (
        ("insurer_number", ""),
        ("insurer_number", "   "),
        ("insured_symbol", ""),
        ("insured_symbol", "   "),
        ("insured_number", ""),
        ("insured_number", "   "),
    ),
    ids=("保険者番号空", "保険者番号空白", "記号空", "記号空白", "番号空", "番号空白"),
)
def test_tc48_構造化保険の必須値が空なら422で拒否する(
    client: TestClient,
    nsips_fixture: NsipsFixture,
    field_name: str,
    invalid_value: str,
) -> None:
    """空・空白だけの必須保険値を無言で省略せず、書込み前に拒否する。"""
    structured_bundle = copy.deepcopy(_valid_structured_bundle())
    structured_bundle["insurance"][field_name] = invalid_value
    response = client.post(
        f"/corporates/{nsips_fixture.corporate_id.value}/stores/{nsips_fixture.store_id.value}/integrations/nsips",
        json={
            "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
            "reception_id": str(uuid.uuid7()),
            "structured_bundle": structured_bundle,
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


def _valid_structured_bundle() -> dict[str, Any]:
    """境界検証で使う、構造化NSIPSの最小有効例を返す。"""
    return {
        "header_version": "1.0",
        "patient": {
            "external_patient_id": "P-HTTP-VALIDATION",
            "kanji_name": "構造化 花子",
            "kana_name": "コウゾウカ ハナコ",
            "birth_date": "1990-01-01",
            "gender": "1",
            "postal_code": "0012345",
            "address": "東京都中央区一丁目2番地",
            "phone_number": "03-1234-5678",
        },
        "prescription": {
            "document_number": "DOC-HTTP-VALIDATION",
            "issued_date": "2026-09-20",
            "institution_code": "1310001",
            "institution_name": "中央診療所",
            "doctor_name": "佐藤医師",
            "doctor_kana": "ヤマダ ハナコ",
            "rps": [
                {
                    "rp_number": 1,
                    "group_name": "内服",
                    "instructions": "1日1回",
                    "dispensing_quantity": 7,
                    "medicines": [
                        {
                            "medicine_code": "610406001",
                            "medicine_name": "アムロジピン",
                            "dosage": "1",
                            "unit": "錠",
                        }
                    ],
                }
            ],
        },
        "dispensed_date": "2026-09-22",
        "insurance": {
            "insurer_number": "138001",
            "insured_symbol": "記号X",
            "insured_number": "番号789",
            "branch_number": "01",
            "insured_type": "self",
            "benefit_ratio": 70,
        },
        "additions": [
            {
                "code": "140000110",
                "name": "特定薬剤管理指導加算２",
                "points": 100,
                "quantity": 1,
            }
        ],
    }


def _remove_nested_value(value: dict[str, Any], path: tuple[str | int, ...]) -> None:
    """テスト用の構造化Bundleから指定した必須項目を取り除く。"""
    parent: Any = value
    for key in path[:-1]:
        parent = parent[key]
    del parent[path[-1]]


@pytest.mark.parametrize(
    "missing_path",
    (
        ("patient",),
        ("patient", "birth_date"),
        ("prescription", "document_number"),
        ("prescription", "rps", 0, "medicines", 0, "unit"),
    ),
    ids=("患者", "生年月日", "処方箋番号", "薬品単位"),
)
def test_tc37_構造化JSONの必須項目欠損は422で拒否する(
    client: TestClient,
    nsips_fixture: NsipsFixture,
    missing_path: tuple[str | int, ...],
) -> None:
    """階層内の必須項目が欠けてもKeyErrorの500や部分書込みにしない。"""
    structured_bundle = _valid_structured_bundle()
    _remove_nested_value(structured_bundle, missing_path)
    response = client.post(
        f"/corporates/{nsips_fixture.corporate_id.value}/stores/{nsips_fixture.store_id.value}/integrations/nsips",
        json={
            "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
            "reception_id": str(uuid.uuid7()),
            "structured_bundle": structured_bundle,
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


@pytest.mark.parametrize("invalid_kind", ("date", "decimal", "list"))
def test_tc38_構造化JSONの型と形式不正は422で拒否する(
    client: TestClient,
    nsips_fixture: NsipsFixture,
    invalid_kind: str,
) -> None:
    """不正な日付・数値・配列形状を低レベル例外や500へ漏らさない。"""
    structured_bundle = _valid_structured_bundle()
    if invalid_kind == "date":
        structured_bundle["prescription"]["issued_date"] = "2026-99-99"
    elif invalid_kind == "decimal":
        structured_bundle["prescription"]["rps"][0]["medicines"][0]["dosage"] = "一錠"
    else:
        structured_bundle["prescription"]["rps"] = "not-a-list"

    response = client.post(
        f"/corporates/{nsips_fixture.corporate_id.value}/stores/{nsips_fixture.store_id.value}/integrations/nsips",
        json={
            "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
            "reception_id": str(uuid.uuid7()),
            "structured_bundle": structured_bundle,
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


@pytest.mark.parametrize("source_mode", ("both", "neither"))
def test_tc39_rawと構造化入力はちょうど一方だけ受け付ける(
    client: TestClient,
    nsips_fixture: NsipsFixture,
    source_mode: str,
) -> None:
    """rawテキストと構造化入力の両方指定・両方未指定を422にする。"""
    payload: dict[str, Any] = {
        "dispenser_staff_id": str(nsips_fixture.pharmacist_id.value),
    }
    if source_mode == "both":
        payload["raw_nsips_text"] = "INVALID"
        payload["structured_bundle"] = _valid_structured_bundle()

    response = client.post(
        f"/corporates/{nsips_fixture.corporate_id.value}/stores/{nsips_fixture.store_id.value}/integrations/nsips",
        json=payload,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert fixture_is_empty(nsips_fixture)


def fixture_is_empty(fixture: NsipsFixture) -> bool:
    """境界エラーの前にFake Repositoryへ何も書いていないことを返す。"""
    return not any(
        (
            fixture.patient_repo.items,
            fixture.patient_external_id_repo.items,
            fixture.patient_coverage_repo.items,
            fixture.coverage_selection_repo.items,
            fixture.prescription_repo.items,
            fixture.dispensing_repo.items,
            fixture.medication_history_repo.items,
            fixture.reception_repo.items,
        )
    )
