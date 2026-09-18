"""法人検索と店舗ライフサイクルのHTTP契約。"""

import pytest

from tests.presentational.conftest import AUTHORIZED_HEADERS, Api


def _store(api: Api) -> tuple[str, str]:
    corporate = api.client.post(
        "/corporates",
        headers=AUTHORIZED_HEADERS,
        json={
            "name": "管理対象法人",
            "representative_last_name": "山田",
            "representative_first_name": "太郎",
        },
    )
    assert corporate.status_code == 201, corporate.text
    corporate_id = str(corporate.json()["id"])
    store = api.client.post(
        f"/corporates/{corporate_id}/stores",
        headers=AUTHORIZED_HEADERS,
        json={
            "name": "対象薬局",
            "name_kana": "タイショウヤッキョク",
            "postal_code": "1234567",
            "address": "東京都千代田区1",
            "phone_number": "0312345678",
        },
    )
    assert store.status_code == 201, store.text
    return corporate_id, str(store.json()["id"])


@pytest.mark.parametrize("limit", ["0", "101", "整数でない"])
def test_法人検索で不正な件数を指定すると共通形式の入力エラーになる(
    api: Api, limit: str
) -> None:
    response = api.client.get(
        "/corporates", params={"limit": limit}, headers=AUTHORIZED_HEADERS
    )
    assert response.status_code == 422, response.text
    assert set(response.json()) == {"code", "message", "errors"}


def test_法人検索で不正なカーソルを拒否する(api: Api) -> None:
    response = api.client.get(
        "/corporates", params={"cursor": "不正値"}, headers=AUTHORIZED_HEADERS
    )
    assert response.status_code == 422, response.text


def test_店舗を休止して再開し閉局した履歴を取得できる(api: Api) -> None:
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"
    for operation, expected in [
        ("suspension", "suspended"),
        ("resumption", "active"),
        ("closure", "closed"),
    ]:
        response = api.client.post(
            f"{prefix}/{operation}",
            json={"reason": "管理者による変更"},
            headers=AUTHORIZED_HEADERS,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected
    history = api.client.get(f"{prefix}/status-history", headers=AUTHORIZED_HEADERS)
    assert history.status_code == 200, history.text
    assert [item["after"] for item in history.json()] == [
        "suspended",
        "active",
        "closed",
    ]


@pytest.mark.parametrize("field", ["person_id", "account_id", "recorded_at"])
def test_店舗状態変更の操作者と日時を本文から指定できない(api: Api, field: str) -> None:
    corporate_id, store_id = _store(api)
    response = api.client.post(
        f"/corporates/{corporate_id}/stores/{store_id}/suspension",
        json={"reason": "休止", field: "偽装値"},
        headers=AUTHORIZED_HEADERS,
    )
    assert response.status_code == 422, response.text
    stored = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}", headers=AUTHORIZED_HEADERS
    )
    assert stored.status_code == 200
    assert stored.json()["status"] == "active"


@pytest.mark.parametrize("operation", ["suspension", "resumption", "closure"])
def test_新しい店舗状態ルートも認証を要求する(api: Api, operation: str) -> None:
    corporate_id, store_id = _store(api)
    response = api.client.post(
        f"/corporates/{corporate_id}/stores/{store_id}/{operation}",
        json={"reason": "操作"},
    )
    assert response.status_code == 401, response.text


def test_招待受諾は未接続の本人確認を素通りしない(api: Api) -> None:
    response = api.client.post(
        "/user-invitations/acceptance", json={"secret": "招待秘密"}
    )
    assert response.status_code == 401, response.text


@pytest.mark.parametrize(
    "method,suffix",
    [
        ("GET", "users"),
        ("GET", "users/user"),
        ("POST", "users/user/suspension"),
        ("POST", "users/user/reactivation"),
        ("POST", "user-invitations/invite/cancellation"),
        ("POST", "people"),
        ("POST", "staffs/staff/person-link"),
        ("GET", "stores/store/manager-assignments"),
        ("POST", "stores/store/manager-assignments/assignment/ending"),
        ("POST", "stores/store/manager-assignments/assignment/cancellation"),
        ("POST", "stores/store/manager-replacement"),
    ],
)
def test_管理機能の追加ルートは認証なしでは開かない(
    api: Api, method: str, suffix: str
) -> None:
    response = api.client.request(method, f"/corporates/corporate/{suffix}", json={})
    assert response.status_code == 401, response.text
