"""開局時間の登録と開局状況照会のHTTP契約。"""

from typing import cast

import pytest
from httpx import Response

from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.test_organization_management import _store

#: 平日の開局。昼休みで2つに分かれる。
_SLOTS = [
    {"opens_at": "09:00:00", "closes_at": "13:00:00"},
    {"opens_at": "14:00:00", "closes_at": "19:00:00"},
]

_WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _weekly(closed: set[str] | None = None) -> list[dict[str, object]]:
    rest = closed if closed is not None else {"sunday"}
    return [
        {"weekday": day, "slots": [] if day in rest else _SLOTS} for day in _WEEKDAYS
    ]


def _register(api: Api, prefix: str, body: dict[str, object]) -> Response:
    return cast(
        Response,
        api.client.put(
            f"{prefix}/business-hours", headers=AUTHORIZED_HEADERS, json=body
        ),
    )


def test_開局時間を登録して店舗詳細から取得できる(api: Api) -> None:
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"

    # Act
    registered = _register(
        api,
        prefix,
        {
            "weekly": _weekly(),
            "exceptions": [
                {"on": "2026-12-31", "slots": [], "note": "年末年始"},
            ],
        },
    )

    # Assert
    assert registered.status_code == 200, registered.text
    body = registered.json()
    assert [item["weekday"] for item in body["weekly"]] == _WEEKDAYS
    assert body["exceptions"][0]["note"] == "年末年始"
    detail = api.client.get(prefix, headers=AUTHORIZED_HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["business_hours"]["weekly"][0]["slots"] == _SLOTS


def test_曜日を欠いた開局時間は入力エラーになる(api: Api) -> None:
    """宣言の無い曜日を定休日に倒さない、という規則をHTTPからも確かめる。"""
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"

    # Act
    response = _register(api, prefix, {"weekly": _weekly()[:-1]})

    # Assert
    assert response.status_code == 422, response.text
    assert set(response.json()) == {"code", "message", "errors"}


def test_開局時間の未知の項目は拒否される(api: Api) -> None:
    """項目名を打ち間違えた変更要求が、成功したのに何も変わらない応答にならない。"""
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"

    # Act
    response = _register(api, prefix, {"weekly": _weekly(), "holidays": []})

    # Assert
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        ("2026-09-17T12:00:00+09:00", "open"),
        ("2026-09-17T13:30:00+09:00", "closed"),
        ("2026-09-20T12:00:00+09:00", "closed"),
        ("2026-09-17T03:00:00Z", "open"),
    ],
    ids=["昼", "昼休み", "日曜", "UTC指定でも日本時間で判定"],
)
def test_指定した日時の開局状況を返す(api: Api, at: str, expected: str) -> None:
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"
    assert _register(api, prefix, {"weekly": _weekly()}).status_code == 200

    # Act
    response = api.client.get(
        f"{prefix}/opening-status", params={"at": at}, headers=AUTHORIZED_HEADERS
    )

    # Assert
    assert response.status_code == 200, response.text
    assert response.json()["state"] == expected


def test_開局時間が未登録の店舗は判定できないと返す(api: Api) -> None:
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"

    # Act
    response = api.client.get(
        f"{prefix}/opening-status",
        params={"at": "2026-09-17T12:00:00+09:00"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "unknown"
    assert response.json()["slots"] == []


def test_タイムゾーンの無い日時での照会は拒否される(api: Api) -> None:
    # Arrange
    corporate_id, store_id = _store(api)
    prefix = f"/corporates/{corporate_id}/stores/{store_id}"

    # Act
    response = api.client.get(
        f"{prefix}/opening-status",
        params={"at": "2026-09-17T12:00:00"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == 422, response.text
