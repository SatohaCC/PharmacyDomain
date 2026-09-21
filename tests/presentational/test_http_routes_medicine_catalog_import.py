"""医薬品マスタCSVインポートのHTTPルートテスト (TC-26〜TC-29)。"""

from __future__ import annotations

from http import HTTPStatus

from app.application.access_control import ActorContext, AuthorizationService
from app.domain.corporate.primitives import CorporateId
from app.presentational.dependencies import get_medicine_catalog_use_cases
from tests.presentational.conftest import AUTHORIZED_HEADERS, Api
from tests.presentational.helpers import create_medicine_catalog_use_cases


def test_CSVアップロードで201が返る(api: Api) -> None:
    """TC-26: ベンダー管理者認証で POST /medicines/import-csv に有効なCSVを送信すると 201 Created が返る。"""
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    )
    res = api.client.post(
        "/medicines/import-csv",
        json={"csv_text": csv_text},
        headers=AUTHORIZED_HEADERS,
    )
    assert res.status_code == HTTPStatus.CREATED
    body = res.json()
    assert body["total_rows"] == 1
    assert body["imported_count"] == 1


def test_法人管理者によるインポートは403(api: Api) -> None:
    """TC-27: 法人管理者の認可コンテキストでアクセスすると 403 Forbidden が返る。"""
    # 法人管理者の認可でユースケース束をオーバーライド
    corp_admin_auth = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="test-corp-admin", corporate_id=CorporateId.generate()
        )
    )
    api.client.app.dependency_overrides[get_medicine_catalog_use_cases] = (  # type: ignore[attr-defined]
        lambda: create_medicine_catalog_use_cases(
            api.medicines, authorization=corp_admin_auth
        )
    )
    try:
        csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール","ニプロ","","",""\n'
        res = api.client.post(
            "/medicines/import-csv",
            json={"csv_text": csv_text},
            headers=AUTHORIZED_HEADERS,
        )
        assert res.status_code == HTTPStatus.FORBIDDEN
    finally:
        api.client.app.dependency_overrides.pop(  # type: ignore[attr-defined]
            get_medicine_catalog_use_cases, None
        )


def test_未認証アクセスは401(api: Api) -> None:
    """TC-28: Authorizationヘッダ無しのアクセスは 401 Unauthorized が返る。"""
    res = api.client.post(
        "/medicines/import-csv",
        json={"csv_text": "sample"},
    )
    assert res.status_code == HTTPStatus.UNAUTHORIZED


def test_不正CSVアップロードは422(api: Api) -> None:
    """TC-29: 構文不正なCSVを送信した場合 422 Unprocessable Content が返る。"""
    res = api.client.post(
        "/medicines/import-csv",
        json={"csv_text": "INVALID_ROW_WITHOUT_COLUMNS"},
        headers=AUTHORIZED_HEADERS,
    )
    assert res.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
