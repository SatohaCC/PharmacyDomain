"""店舗許認可APIのテスト（TC-007, TC-008）。"""

from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.presentational.dependencies import get_actor_context, get_store_use_cases
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.helpers import create_store_use_cases, vendor_admin


def _create_store(
    api: Api, corporate_name: str = "許認可テスト法人"
) -> tuple[str, str]:
    corporate = api.client.post(
        "/corporates",
        headers=AUTHORIZED_HEADERS,
        json={
            "name": corporate_name,
            "representative_last_name": "山田",
            "representative_first_name": "太郎",
        },
    )
    assert corporate.status_code == HTTPStatus.CREATED, corporate.text
    corporate_id = str(corporate.json()["id"])
    store = api.client.post(
        f"/corporates/{corporate_id}/stores",
        headers=AUTHORIZED_HEADERS,
        json={
            "name": f"{corporate_name}店",
            "name_kana": "キョニンカテストテン",
            "postal_code": "100-0001",
            "address": "千代田区1-1",
            "phone_number": "03-1111-2222",
        },
    )
    assert store.status_code == HTTPStatus.CREATED, store.text
    return corporate_id, str(store.json()["id"])


def _set_actor(client: TestClient, api: Api, actor: ResolvedActorContext) -> None:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_actor_context] = lambda: actor
    app.dependency_overrides[get_store_use_cases] = lambda: create_store_use_cases(
        api.stores, api.corporates, actor=actor
    )


def test_TC007_法人管理者が免許を全体置換し詳細取得できる(api: Api) -> None:
    corporate_id, store_id = _create_store(api)

    # 法人管理者Actorを構成
    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    corp_id = CorporateId.parse(corporate_id)
    corp_admin_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=corp_id,
    )
    _set_actor(api.client, api, corp_admin_actor)

    # 1. 薬局開設許可＋麻薬小売業者免許をPUT
    put_response = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/licenses",
        headers=AUTHORIZED_HEADERS,
        json={
            "pharmacy_license": {
                "number": "薬-2026-001",
                "valid_from": "2026-10-29",
                "valid_to": "2032-10-28",
            },
            "narcotics_retailer_license": {
                "number": "麻-2026-001",
                "valid_from": "2026-10-29",
                "valid_to": "2028-12-31",
            },
        },
    )
    assert put_response.status_code == HTTPStatus.NO_CONTENT, put_response.text

    # GET詳細取得で反映されていることを確認
    get_response = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}",
        headers=AUTHORIZED_HEADERS,
    )
    assert get_response.status_code == HTTPStatus.OK, get_response.text
    detail = get_response.json()
    assert detail["licenses"] is not None
    assert detail["licenses"]["pharmacy_license"]["number"] == "薬-2026-001"
    assert detail["licenses"]["pharmacy_license"]["valid_from"] == "2026-10-29"
    assert detail["licenses"]["pharmacy_license"]["valid_to"] == "2032-10-28"
    assert detail["licenses"]["narcotics_retailer_license"]["number"] == "麻-2026-001"
    assert detail["licenses"]["narcotics_retailer_license"]["valid_to"] == "2028-12-31"

    # 2. 麻薬免許を null に全体置換
    put_null_resp = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/licenses",
        headers=AUTHORIZED_HEADERS,
        json={
            "pharmacy_license": {
                "number": "薬-2026-001",
                "valid_from": "2026-10-29",
                "valid_to": "2032-10-28",
            },
            "narcotics_retailer_license": None,
        },
    )
    assert put_null_resp.status_code == HTTPStatus.NO_CONTENT, put_null_resp.text

    # 再度GETで麻薬免許が消えていることを確認
    get_null_resp = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}",
        headers=AUTHORIZED_HEADERS,
    )
    assert get_null_resp.status_code == HTTPStatus.OK
    assert get_null_resp.json()["licenses"]["narcotics_retailer_license"] is None


def test_TC007_満了日不正の全体置換は設定と保存回数を変えない(api: Api) -> None:
    corporate_id, store_id = _create_store(api)

    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    corp_admin_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=CorporateId.parse(corporate_id),
    )
    _set_actor(api.client, api, corp_admin_actor)

    # 麻薬免許の満了日が翌々年末（2028-12-31）ではない不正日（2028-12-30）でPUT
    response = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/licenses",
        headers=AUTHORIZED_HEADERS,
        json={
            "pharmacy_license": {
                "number": "薬-2026-001",
                "valid_from": "2026-10-29",
                "valid_to": "2032-10-28",
            },
            "narcotics_retailer_license": {
                "number": "麻-2026-001",
                "valid_from": "2026-10-29",
                "valid_to": "2028-12-30",
            },
        },
    )
    # 422 Unprocessable Entity（DomainValidationError）
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text

    # 店舗のlicensesは未設定のまま
    get_resp = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}",
        headers=AUTHORIZED_HEADERS,
    )
    assert get_resp.status_code == HTTPStatus.OK
    assert get_resp.json()["licenses"] is None


def test_TC008_一般職と店舗管理者の免許更新を拒否する(api: Api) -> None:
    corporate_id, store_id = _create_store(api)
    sid = StoreId.parse(store_id)
    cid = CorporateId.parse(corporate_id)

    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)

    valid_payload = {
        "pharmacy_license": {
            "number": "薬-2026-001",
            "valid_from": "2026-10-29",
            "valid_to": "2032-10-28",
        },
        "narcotics_retailer_license": None,
    }

    # 一般職（STORE_OPERATOR）
    operator_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=cid,
        store_ids=frozenset({sid}),
        managed_store_ids=frozenset(),
    )
    _set_actor(api.client, api, operator_actor)
    op_resp = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/licenses",
        headers=AUTHORIZED_HEADERS,
        json=valid_payload,
    )
    assert op_resp.status_code == HTTPStatus.FORBIDDEN, op_resp.text

    # 店舗管理者（STORE_MANAGER）
    manager_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.STORE_MANAGER}),
        corporate_id=cid,
        store_ids=frozenset({sid}),
        managed_store_ids=frozenset({sid}),
    )
    _set_actor(api.client, api, manager_actor)
    mgr_resp = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/licenses",
        headers=AUTHORIZED_HEADERS,
        json=valid_payload,
    )
    assert mgr_resp.status_code == HTTPStatus.FORBIDDEN, mgr_resp.text


def test_TC008_別法人店舗への免許更新は404で設定を保持する(api: Api) -> None:
    corp_a, store_a = _create_store(api, corporate_name="許認可テスト法人A")
    corp_b, store_b = _create_store(api, corporate_name="許認可テスト法人B")

    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    # 法人Aの管理者
    corp_a_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=CorporateId.parse(corp_a),
    )
    _set_actor(api.client, api, corp_a_actor)

    valid_payload = {
        "pharmacy_license": {
            "number": "薬-2026-001",
            "valid_from": "2026-10-29",
            "valid_to": "2032-10-28",
        },
        "narcotics_retailer_license": None,
    }

    # 法人Aの管理者が法人Bの店舗を更新しようとする
    resp = api.client.put(
        f"/corporates/{corp_b}/stores/{store_b}/licenses",
        headers=AUTHORIZED_HEADERS,
        json=valid_payload,
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND, resp.text
