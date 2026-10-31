"""ポリシーAPIのプレゼンテーション層テスト（TC-074, TC-075, TC-082）。

- TC-074: ポリシーAPI/値異常（422）
- TC-075: ポリシー/管理認可（403, 404, 204）
- TC-082: 実効Query/副作用なし（GET /effective-policy）
"""

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
from app.presentational.dependencies import (
    get_actor_context,
    get_corporate_use_cases,
    get_store_use_cases,
)
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.helpers import (
    create_corporate_use_cases,
    create_store_use_cases,
    vendor_admin,
)


def _create_store(
    api: Api, corporate_name: str = "ポリシーテスト法人"
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
            "name_kana": "ポリシテストテン",
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
    app.dependency_overrides[get_corporate_use_cases] = lambda: (
        create_corporate_use_cases(api.corporates, actor=actor)
    )
    app.dependency_overrides[get_store_use_cases] = lambda: create_store_use_cases(
        api.stores, api.corporates, actor=actor
    )


def test_TC074_ポリシーAPI_値異常_未知キーや不正文字列boolは422で元設定保持(
    api: Api,
) -> None:
    corporate_id, store_id = _create_store(api)

    # 1. Corporate ポリシーに未知キー -> 422
    resp_unknown_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": True, "overridable": True},
            "prohibit_self_verification": {"value": True, "overridable": True},
            "unknown_setting": {"value": True},
        },
    )
    assert resp_unknown_corp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 2. Corporate ポリシーに文字列bool -> 422
    resp_invalid_bool = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {
                "value": "not-a-bool",
                "overridable": True,
            },
            "prohibit_self_verification": {"value": False, "overridable": False},
        },
    )
    assert resp_invalid_bool.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 3. Store ポリシーに未知キー -> 422
    resp_unknown_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": True,
            "prohibit_self_verification": True,
            "extra_key": "forbidden",
        },
    )
    assert resp_unknown_store.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 4. 元の設定値が変更されず維持されていることを確認
    corp_get = api.client.get(
        f"/corporates/{corporate_id}",
        headers=AUTHORIZED_HEADERS,
    )
    assert corp_get.status_code == HTTPStatus.OK
    corp_policy = corp_get.json()["policy"]
    assert corp_policy["require_prescription_audit"]["value"] is False
    assert corp_policy["prohibit_self_verification"]["value"] is False


def test_TC075_ポリシー_管理認可_権限不足403_他法人404_自法人管理者204(
    api: Api,
) -> None:
    corporate_id, store_id = _create_store(api)
    base_actor = vendor_admin()
    assert isinstance(base_actor, ResolvedActorContext)
    corp_id = CorporateId.parse(corporate_id)
    s_id = StoreId.parse(store_id)

    # 1. 一般職 (STORE_OPERATOR) -> 法人/店舗とも 403
    staff_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=corp_id,
        store_ids=frozenset({s_id}),
    )
    _set_actor(api.client, api, staff_actor)

    resp_staff_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": True, "overridable": False},
            "prohibit_self_verification": {"value": True, "overridable": False},
        },
    )
    assert resp_staff_corp.status_code == HTTPStatus.FORBIDDEN

    resp_staff_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": True,
        },
    )
    assert resp_staff_store.status_code == HTTPStatus.FORBIDDEN

    # 2. 店舗管理者 (STORE_MANAGER) -> 法人/店舗とも 403 (MANAGE_CORPORATE/MANAGE_STORE権限なし)
    mgr_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.STORE_MANAGER}),
        corporate_id=corp_id,
        store_ids=frozenset({s_id}),
        managed_store_ids=frozenset({s_id}),
    )
    _set_actor(api.client, api, mgr_actor)

    resp_mgr_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": True, "overridable": False},
            "prohibit_self_verification": {"value": True, "overridable": False},
        },
    )
    assert resp_mgr_corp.status_code == HTTPStatus.FORBIDDEN

    resp_mgr_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": True,
        },
    )
    assert resp_mgr_store.status_code == HTTPStatus.FORBIDDEN

    # 3. 他法人管理者 (別法人ID) -> 404
    other_corp_id = CorporateId.generate()
    other_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=other_corp_id,
    )
    _set_actor(api.client, api, other_actor)

    resp_other_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": True, "overridable": False},
            "prohibit_self_verification": {"value": True, "overridable": False},
        },
    )
    assert resp_other_corp.status_code == HTTPStatus.NOT_FOUND

    resp_other_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": True,
        },
    )
    assert resp_other_store.status_code == HTTPStatus.NOT_FOUND

    # 4. 自法人管理者 (CORPORATE_ADMIN) -> 204 No Content
    own_admin_actor = replace(
        base_actor,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=corp_id,
    )
    _set_actor(api.client, api, own_admin_actor)

    resp_own_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": False, "overridable": True},
            "prohibit_self_verification": {"value": False, "overridable": True},
        },
    )
    assert resp_own_corp.status_code == HTTPStatus.NO_CONTENT

    resp_own_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": True,
            "prohibit_self_verification": True,
        },
    )
    assert resp_own_store.status_code == HTTPStatus.NO_CONTENT


def test_TC082_実効Query_副作用なし_表示値と業務判定一致_複数回取得でも状態不変(
    api: Api,
) -> None:
    corporate_id, store_id = _create_store(api)

    # 1. 初期状態の実効ポリシー取得
    resp_init = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}/effective-policy",
        headers=AUTHORIZED_HEADERS,
    )
    assert resp_init.status_code == HTTPStatus.OK
    init_data = resp_init.json()
    assert init_data["require_prescription_audit"]["value"] is False
    assert init_data["require_prescription_audit"]["source"] == "corporate"
    assert init_data["prohibit_self_verification"]["value"] is False
    assert init_data["prohibit_self_verification"]["source"] == "corporate"

    # 2. 法人ポリシーを更新 (require_prescription_audit: True, overridable: True)
    resp_put_corp = api.client.put(
        f"/corporates/{corporate_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": {"value": True, "overridable": True},
            "prohibit_self_verification": {"value": False, "overridable": False},
        },
    )
    assert resp_put_corp.status_code == HTTPStatus.NO_CONTENT

    # 3. 複数回 GET を実行しても状態不変で同一結果を返す
    for _ in range(3):
        resp_eff = api.client.get(
            f"/corporates/{corporate_id}/stores/{store_id}/effective-policy",
            headers=AUTHORIZED_HEADERS,
        )
        assert resp_eff.status_code == HTTPStatus.OK
        eff_data = resp_eff.json()
        assert eff_data["require_prescription_audit"]["value"] is True
        assert eff_data["require_prescription_audit"]["source"] == "corporate"
        assert eff_data["prohibit_self_verification"]["value"] is False
        assert eff_data["prohibit_self_verification"]["source"] == "corporate"

    # 4. 店舗ポリシーを上書き (require_prescription_audit: False)
    resp_put_store = api.client.put(
        f"/corporates/{corporate_id}/stores/{store_id}/policy",
        headers=AUTHORIZED_HEADERS,
        json={
            "require_prescription_audit": False,
        },
    )
    assert resp_put_store.status_code == HTTPStatus.NO_CONTENT

    # 5. 実効値が店舗上書き値（False）へ切り替わっていることを確認
    resp_eff_store = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}/effective-policy",
        headers=AUTHORIZED_HEADERS,
    )
    assert resp_eff_store.status_code == HTTPStatus.OK
    eff_store_data = resp_eff_store.json()
    assert eff_store_data["require_prescription_audit"]["value"] is False
    assert eff_store_data["require_prescription_audit"]["source"] == "store"
    assert eff_store_data["prohibit_self_verification"]["value"] is False
    assert eff_store_data["prohibit_self_verification"]["source"] == "corporate"
