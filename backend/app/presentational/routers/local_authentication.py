"""ログインと初回パスワード変更のHTTP境界。"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import Field

from app.application.identity.boundary_interfaces.local_authentication import (
    LocalAuthentication,
)
from app.application.identity.boundary_models import LoginSession
from app.presentational.dependencies import PresentationState, bearer_scheme, get_state
from app.presentational.errors import error_responses
from app.presentational.exceptions import AuthenticationError
from app.presentational.routing import ApplicationRoute
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    route_class=ApplicationRoute,
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


def get_local_authentication(
    state: Annotated[PresentationState, Depends(get_state)],
) -> LocalAuthentication:
    """構成済みのローカル認証だけを提供する。"""
    if state.local_authentication is None:
        raise AuthenticationError("ローカル認証が接続されていません。")
    return state.local_authentication


Auth = Annotated[LocalAuthentication, Depends(get_local_authentication)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


class LoginRequest(RequestModel):
    """ログイン入力。秘密をモデルの文字列表現へ含めない。"""

    corporate_id: str
    email: str = Field(max_length=256)
    password: str = Field(repr=False, max_length=128)


class VendorLoginRequest(RequestModel):
    """運営者のログイン入力。"""

    email: str = Field(max_length=256)
    password: str = Field(repr=False, max_length=128)


class ChangePasswordRequest(RequestModel):
    """変更専用セッションでも使えるパスワード変更入力。"""

    password: str = Field(repr=False, min_length=15, max_length=128)


class SelectStoreContextRequest(RequestModel):
    """作業対象とする店舗の選択入力。"""

    store_id: str


@router.post("/login", response_model=LoginSession)
async def login(body: LoginRequest, auth: Auth, response: Response) -> LoginSession:
    """初期パスワードでは変更専用セッションを返す。"""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return await auth.login(body.corporate_id, body.email, body.password)


@router.post("/vendor/login", response_model=LoginSession)
async def vendor_login(
    body: VendorLoginRequest, auth: Auth, response: Response
) -> LoginSession:
    """運営者の資格情報を照合しセッションを発行する。"""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return await auth.vendor_login(body.email, body.password)


@router.post("/password", response_model=LoginSession)
async def change_password(
    body: ChangePasswordRequest,
    auth: Auth,
    credentials: Credentials,
    response: Response,
) -> LoginSession:
    """既存セッションを失効して変更後のセッションを返す。"""
    response.headers["Cache-Control"] = "no-store"
    if credentials is None:
        raise AuthenticationError()
    return await auth.change_password(credentials.credentials, body.password)


@router.post("/store-context", response_model=LoginSession)
async def select_store_context(
    body: SelectStoreContextRequest,
    auth: Auth,
    credentials: Credentials,
    response: Response,
) -> LoginSession:
    """許可・所属済みの店舗を選択した新しいセッションを発行する。"""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if credentials is None:
        raise AuthenticationError()
    return await auth.select_store(credentials.credentials, body.store_id)


@router.post("/logout", status_code=204)
async def logout(auth: Auth, credentials: Credentials) -> None:
    """サーバー上のセッションを削除する。"""
    if credentials is not None:
        await auth.logout(credentials.credentials)
