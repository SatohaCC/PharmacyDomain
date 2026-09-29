"""患者頭書きHTTPの入力・応答契約。"""

from dataclasses import replace
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.lifecycle import PatientStatus
from app.domain.patient.primitives import PatientId
from app.presentational.dependencies import get_patient_use_cases
from tests.factories.persistence_factory import create_patient
from tests.fakes.stub_actor_context_provider import VALID_TOKEN
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.helpers import create_patient_use_cases, vendor_admin


def _patient_heading_url(api: Api) -> tuple[str, str]:
    """HTTP経由の法人を用意し、その配下に患者を登録する。"""
    response = api.client.post(
        "/corporates",
        json={
            "name": "頭書き法人",
            "representative_last_name": "山田",
            "representative_first_name": "太郎",
        },
        headers=AUTHORIZED_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    corporate_id: str = response.json()["id"]
    patient = create_patient(corporate_id=CorporateId.parse(corporate_id))
    api.patients.items[patient.id] = patient
    return (
        corporate_id,
        f"/corporates/{corporate_id}/patients/{patient.id.value}/heading",
    )


def _use_actor(client: TestClient, api: Api, actor: ResolvedActorContext) -> None:
    """HTTP ActorとUseCaseの認可主体をそろえる。"""
    application = cast(FastAPI, client.app)
    application.dependency_overrides[get_patient_use_cases] = lambda: (
        create_patient_use_cases(
            api.patients, api.external_identifiers, api.corporates, actor=actor
        )
    )


def test_tc43_29_HTTPから頭書きを登録し解除して読み戻せる(api: Api) -> None:
    corporate_id, url = _patient_heading_url(api)
    initial = api.client.get(url, headers=AUTHORIZED_HEADERS)
    assert initial.status_code == HTTPStatus.OK, initial.text
    assert initial.json()["revision"] == 0
    assert initial.json()["history"] == []

    created = api.client.patch(
        url,
        json={
            "expected_revision": 0,
            "summary": "来局時の注意",
            "notes": "前回の経緯\n申し送り",
        },
        headers=AUTHORIZED_HEADERS,
    )
    assert created.status_code == HTTPStatus.OK, created.text
    assert created.json()["revision"] == 1
    assert created.json()["history"][0]["notes"] == "前回の経緯\n申し送り"

    cleared = api.client.patch(
        url,
        json={"expected_revision": 1, "summary": None},
        headers=AUTHORIZED_HEADERS,
    )
    assert cleared.status_code == HTTPStatus.OK, cleared.text
    assert cleared.json()["summary"] is None
    assert cleared.json()["notes"] == "前回の経緯\n申し送り"
    assert cleared.json()["revision"] == 2
    assert len(cleared.json()["history"]) == 2
    assert url.startswith(f"/corporates/{corporate_id}/patients/")


def test_tc43_30_改訂番号なしと項目なしの更新を拒否する(api: Api) -> None:
    _, url = _patient_heading_url(api)

    for body in [{"summary": "記録"}, {"expected_revision": 0}]:
        response = api.client.patch(url, json=body, headers=AUTHORIZED_HEADERS)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
        assert set(response.json()) == {"code", "message", "errors"}


def test_tc43_31_未知項目と不正な改訂番号を拒否する(api: Api) -> None:
    corporate_id, url = _patient_heading_url(api)

    for body in [
        {"expected_revision": -1, "summary": "記録"},
        {"expected_revision": 0, "summary": [], "notes": ""},
        {"expected_revision": 0, "summary": "記録", "unknown": True},
    ]:
        response = api.client.patch(url, json=body, headers=AUTHORIZED_HEADERS)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    patient_id = url.split("/")[-2]
    invalid_paths = [
        f"/corporates/not-a-uuid/patients/{patient_id}/heading",
        f"/corporates/{corporate_id}/patients/not-a-uuid/heading",
    ]
    for path in invalid_paths:
        response = api.client.get(path, headers=AUTHORIZED_HEADERS)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_tc43_32_HTTP本文から記録者と時刻を偽装できない(api: Api) -> None:
    _, url = _patient_heading_url(api)

    for field, value in [
        ("person_id", "00000000-0000-7000-8000-000000000000"),
        ("account_id", "00000000-0000-7000-8000-000000000000"),
        ("recorded_at", "2026-09-01T00:00:00Z"),
        ("updated_at", "2026-09-01T00:00:00Z"),
    ]:
        response = api.client.patch(
            url,
            json={"expected_revision": 0, "summary": "記録", field: value},
            headers=AUTHORIZED_HEADERS,
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_tc43_33_本文の文字数上限をHTTPで守る(api: Api) -> None:
    _, url = _patient_heading_url(api)
    for revision, field in enumerate(("summary", "notes")):
        accepted = api.client.patch(
            url,
            json={"expected_revision": revision, field: "あ" * 10_000},
            headers=AUTHORIZED_HEADERS,
        )
        assert accepted.status_code == HTTPStatus.OK, accepted.text
        too_long = api.client.patch(
            url,
            json={"expected_revision": revision, field: "あ" * 10_001},
            headers=AUTHORIZED_HEADERS,
        )
        assert too_long.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_tc43_34_店舗ビューアは参照できるが更新できない(api: Api) -> None:
    corporate_id, url = _patient_heading_url(api)
    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    actor = replace(
        base_actor,
        principal_id="店舗ビューア",
        roles=frozenset({ActorRole.STORE_VIEWER}),
        corporate_id=next(
            key for key in api.corporates.items if str(key.value) == corporate_id
        ),
    )
    _use_actor(api.client, api, actor)

    visible = api.client.get(url, headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    denied = api.client.patch(
        url,
        json={"expected_revision": 0, "summary": "変更"},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )

    assert visible.status_code == HTTPStatus.OK
    assert denied.status_code == HTTPStatus.FORBIDDEN
    assert set(denied.json()) == {"code", "message", "errors"}

    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    foreign_corporate_id = CorporateId.generate()
    foreign_actor = replace(
        base_actor,
        principal_id="別法人店舗オペレータ",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=foreign_corporate_id,
    )
    _use_actor(api.client, api, foreign_actor)
    foreign = api.client.get(url, headers=AUTHORIZED_HEADERS)
    assert foreign.status_code == HTTPStatus.NOT_FOUND

    local_actor = replace(
        base_actor,
        principal_id="同法人店舗オペレータ",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=actor.corporate_id,
    )
    _use_actor(api.client, api, local_actor)
    missing_patient_id = PatientId.generate()
    missing_url = (
        f"/corporates/{corporate_id}/patients/{missing_patient_id.value}/heading"
    )
    missing_get = api.client.get(missing_url, headers=AUTHORIZED_HEADERS)
    missing_patch = api.client.patch(
        missing_url,
        json={"expected_revision": 0, "summary": "存在しない患者"},
        headers=AUTHORIZED_HEADERS,
    )
    assert missing_get.status_code == HTTPStatus.NOT_FOUND
    assert missing_patch.status_code == HTTPStatus.NOT_FOUND


def test_tc43_35_古い改訂は409で現在値を変えない(api: Api) -> None:
    _, url = _patient_heading_url(api)
    initial = api.client.patch(
        url,
        json={"expected_revision": 0, "summary": "確定値"},
        headers=AUTHORIZED_HEADERS,
    )
    assert initial.status_code == HTTPStatus.OK, initial.text
    conflict = api.client.patch(
        url,
        json={"expected_revision": 0, "summary": "古い入力"},
        headers=AUTHORIZED_HEADERS,
    )
    assert conflict.status_code == HTTPStatus.CONFLICT
    assert conflict.json()["code"] == "PATIENT_HEADING_CONFLICT"
    patient_id = PatientId.parse(url.split("/")[-2])
    current_patient = api.patients.items[patient_id]
    api.patients.items[patient_id] = replace(
        current_patient,
        status=PatientStatus.MERGED,
        merged_into_id=PatientId.generate(),
    )
    merged = api.client.patch(
        url,
        json={"expected_revision": 1, "summary": "統合済みの更新"},
        headers=AUTHORIZED_HEADERS,
    )
    current = api.client.get(url, headers=AUTHORIZED_HEADERS)
    assert merged.status_code == HTTPStatus.CONFLICT
    assert merged.json()["code"] == "PATIENT_STATE_CONFLICT"
    assert current.json()["summary"] == "確定値"
    assert current.json()["revision"] == 1


def test_tc43_36_OpenAPIに頭書き本文と改訂競合を載せる(api: Api) -> None:
    schema: dict[str, Any] = cast(FastAPI, api.client.app).openapi()
    paths = schema["paths"]
    get_path = next(path for path in paths if path.endswith("/heading"))
    get_operation = paths[get_path]["get"]
    patch_operation = paths[get_path]["patch"]

    request_schema = patch_operation["requestBody"]["content"]["application/json"][
        "schema"
    ]
    if "$ref" in request_schema:
        request_schema = schema["components"]["schemas"][
            request_schema["$ref"].rsplit("/", 1)[-1]
        ]
    assert {"expected_revision", "summary", "notes"} <= set(
        request_schema["properties"]
    )
    assert "expected_revision" in request_schema["required"]
    for field in ("summary", "notes"):
        field_schema = request_schema["properties"][field]
        if "$ref" in field_schema:
            field_schema = schema["components"]["schemas"][
                field_schema["$ref"].rsplit("/", 1)[-1]
            ]
        assert field_schema.get("anyOf") is not None
        assert any(option.get("type") == "null" for option in field_schema["anyOf"])
    assert "409" in patch_operation["responses"]
    response_schema = get_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    if "$ref" in response_schema:
        response_schema = schema["components"]["schemas"][
            response_schema["$ref"].rsplit("/", 1)[-1]
        ]
    assert {"revision", "summary", "notes", "history"} <= set(
        response_schema["properties"]
    )
