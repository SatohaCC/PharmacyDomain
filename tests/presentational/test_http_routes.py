"""法人・店舗のHTTPルートの振る舞い。"""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any

from fastapi.testclient import TestClient

from app.presentational import create_app
from tests.fakes.stub_actor_context_provider import StubActorContextProvider
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.helpers import vendor_admin

_CORPORATE_BODY = {
    "name": "サンプル法人",
    "representative_last_name": "山田",
    "representative_first_name": "太郎",
}
_STORE_BODY = {
    "name": "サンプル薬局",
    "name_kana": "サンプルヤッキョク",
    "postal_code": "1234567",
    "address": "東京都千代田区1-2-3",
    "phone_number": "03-1234-5678",
}


def _register_corporate(api: Api) -> str:
    response = api.client.post(
        "/corporates", json=_CORPORATE_BODY, headers=AUTHORIZED_HEADERS
    )
    assert response.status_code == HTTPStatus.CREATED
    corporate_id: str = response.json()["id"]
    return corporate_id


def _register_store(api: Api, corporate_id: str, **overrides: Any) -> str:
    response = api.client.post(
        f"/corporates/{corporate_id}/stores",
        json={**_STORE_BODY, **overrides},
        headers=AUTHORIZED_HEADERS,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    store_id: str = response.json()["id"]
    return store_id


def test_稼働確認は_認証なしで応答する(api: Api) -> None:
    # Act
    response = api.client.get("/health")

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_資格情報の無い業務要求は_401になる(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)

    # Act
    response = api.client.get(f"/corporates/{corporate_id}")

    # Assert: ルータ単位の認証が、ユースケースへ到達する前に落とす。
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_法人を登録すると_採番されたIDが返る(api: Api) -> None:
    # Act
    corporate_id = _register_corporate(api)

    # Assert
    assert len(api.corporates.items) == 1
    assert corporate_id in {str(item.value) for item in api.corporates.items}


def test_登録した法人を取得できる(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)

    # Act
    response = api.client.get(f"/corporates/{corporate_id}", headers=AUTHORIZED_HEADERS)

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": corporate_id,
        "name": "サンプル法人",
        "representative_name": "山田 太郎",
        "is_active": True,
    }


def test_存在しない法人の取得は_404になる(api: Api) -> None:
    # Act
    response = api.client.get(
        "/corporates/01890000-0000-7000-8000-000000000000",
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["code"] == "CORPORATE_NOT_FOUND"


def test_法人IDの形式が不正なら_422になる(api: Api) -> None:
    # Act: ドメインプリミティブの検証エラーが翻訳される。
    response = api.client.get("/corporates/not-a-uuid", headers=AUTHORIZED_HEADERS)

    # Assert
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "DOMAIN_VALIDATION_ERROR"


def test_同名の法人登録は_409になる(api: Api) -> None:
    # Arrange
    _register_corporate(api)

    # Act
    response = api.client.post(
        "/corporates", json=_CORPORATE_BODY, headers=AUTHORIZED_HEADERS
    )

    # Assert
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "CORPORATE_NAME_ALREADY_EXISTS"


def test_未知の項目を含む要求は_422で拒否される(api: Api) -> None:
    # Act: 打ち間違えた項目名を黙って捨てない。
    response = api.client.post(
        "/corporates",
        json={**_CORPORATE_BODY, "represent_last_name": "誤記"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_入力検証の失敗も_ドメインの失敗と同じ形の本文を返す(api: Api) -> None:
    """同じ422で本文の形が2種類あると、クライアントは分岐を書けない。"""
    # Act
    invalid_body = api.client.post(
        "/corporates", json={"name": 1}, headers=AUTHORIZED_HEADERS
    )
    invalid_domain_value = api.client.get(
        "/corporates/not-a-uuid", headers=AUTHORIZED_HEADERS
    )

    # Assert
    assert invalid_body.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert invalid_domain_value.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert set(invalid_body.json()) == set(invalid_domain_value.json())
    assert invalid_body.json()["code"] == "REQUEST_VALIDATION_ERROR"
    # 項目ごとの内容は落とさず ``errors`` に残す。
    assert {"location": "body.name", "message": "Input should be a valid string"} in (
        invalid_body.json()["errors"]
    )
    assert invalid_domain_value.json()["errors"] == []


def test_未知のパスも_同じ形の本文を返す(api: Api) -> None:
    """経路解決の失敗だけ ``detail`` になると、業務の404と食い違う。"""
    # Act
    response = api.client.get("/unknown-path", headers=AUTHORIZED_HEADERS)

    # Assert
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "指定されたリソースが見つかりません。",
        "errors": [],
    }


def test_許可されないメソッドは_Allowヘッダを保ったまま翻訳される(api: Api) -> None:
    # Act
    response = api.client.delete("/health")

    # Assert
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


def test_法人名を変更すると_204で本文を返さない(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)

    # Act
    response = api.client.patch(
        f"/corporates/{corporate_id}/name",
        json={"name": "改名後法人"},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""


def test_店舗を登録して一覧できる(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)
    store_id = _register_store(api, corporate_id)

    # Act
    response = api.client.get(
        f"/corporates/{corporate_id}/stores", headers=AUTHORIZED_HEADERS
    )

    # Assert
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {
            "id": store_id,
            "corporate_id": corporate_id,
            "name": "サンプル薬局",
            "name_kana": "サンプルヤッキョク",
            "code": None,
        }
    ]


def test_店舗の詳細は_未設定の任意項目をnullで返す(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)
    store_id = _register_store(api, corporate_id)

    # Act
    response = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}", headers=AUTHORIZED_HEADERS
    )

    # Assert: 電話番号はドメインプリミティブが区切り記号を落として保持する。
    body = response.json()
    assert response.status_code == HTTPStatus.OK
    assert body["phone_number"] == "0312345678"
    assert body["fax_number"] is None
    assert body["insurance_pharmacy_number"] is None


def test_他法人の店舗は_404として隠される(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)
    store_id = _register_store(api, corporate_id)
    other_corporate_id = api.client.post(
        "/corporates",
        json={**_CORPORATE_BODY, "name": "別のサンプル法人"},
        headers=AUTHORIZED_HEADERS,
    ).json()["id"]

    # Act
    response = api.client.get(
        f"/corporates/{other_corporate_id}/stores/{store_id}",
        headers=AUTHORIZED_HEADERS,
    )

    # Assert: 403 だと「その店舗が存在すること」自体が漏れる。
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["code"] == "STORE_NOT_FOUND"


def test_店舗コードは_空文字の指定で解除される(api: Api) -> None:
    # Arrange
    corporate_id = _register_corporate(api)
    store_id = _register_store(api, corporate_id, code="S001")

    # Act
    response = api.client.patch(
        f"/corporates/{corporate_id}/stores/{store_id}/code",
        json={"code": "   "},
        headers=AUTHORIZED_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.NO_CONTENT
    detail = api.client.get(
        f"/corporates/{corporate_id}/stores/{store_id}", headers=AUTHORIZED_HEADERS
    )
    assert detail.json()["code"] is None


def test_業務ルートは_すべて認証を要求する() -> None:
    """認証を書き忘れた1本だけが無認証で公開されることを防ぐ。

    認証はルータ単位の ``dependencies`` で掛けているので、ルートを足しただけでは
    抜けない。抜けるのは ``dependencies`` を書かずに新しいルータを足したときで、
    それは書いた本人には見えない。依存グラフの形ではなく、公開されている全ルート
    へ実際に無認証で投げて確かめる（FastAPIの内部構造に依存しない）。
    """
    # Arrange: 死活監視だけは認証を通さない（認証基盤の障害と区別するため）。
    unauthenticated_paths = {"/health"}
    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    client = TestClient(app)
    placeholder = "01890000-0000-7000-8000-000000000000"

    # Act
    unprotected: list[str] = []
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if path in unauthenticated_paths:
            continue
        url = re.sub(r"\{[^}]+\}", placeholder, path)
        for method in operations:
            checked += 1
            response = client.request(method.upper(), url, json={})
            if response.status_code != HTTPStatus.UNAUTHORIZED:
                unprotected.append(f"{method.upper()} {path} -> {response.status_code}")

    # Assert
    assert not unprotected, f"認証を要求しないルート: {unprotected}"
    assert checked >= 10, "走査が業務ルートを見つけられていない"


def test_OpenAPIに_Bearer認証が載る() -> None:
    """``/docs`` から資格情報を入れて試せる状態を保つ。"""
    # Arrange
    app = create_app()

    # Act
    schema = app.openapi()

    # Assert
    schemes = schema["components"]["securitySchemes"]
    assert schemes["HTTPBearer"] == {"type": "http", "scheme": "bearer"} | {
        "description": schemes["HTTPBearer"]["description"]
    }
    assert schema["paths"]["/corporates"]["post"]["security"] == [{"HTTPBearer": []}]
    # 認証を通さないルートには付けない。
    assert "security" not in schema["paths"]["/health"]["get"]


def test_OpenAPIに_返しうるエラー応答が載る() -> None:
    """成功応答だけを知っている生成クライアントは、失敗を型として扱えない。"""
    # Arrange
    app = create_app()

    # Act
    schema = app.openapi()
    register = schema["paths"]["/corporates"]["post"]["responses"]
    detail = schema["paths"]["/corporates/{corporate_id}"]["get"]["responses"]

    # Assert
    assert set(register) == {"201", "401", "403", "409", "422"}
    assert set(detail) == {"200", "401", "403", "404", "422"}
    # 422はFastAPIが自動で足す既定（HTTPValidationError）ではなく、共通の形。
    assert (
        register["422"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ErrorResponse"
    )
