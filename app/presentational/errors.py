"""Applicationの失敗分類をHTTPステータスと共通本文へ変換する。

Domain例外の分類はApplicationの公開境界が所有し、HTTPステータスの選択は
このモジュールへ集約する。入力検証と経路解決の失敗も同じ本文形式へ揃える。"""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.common.exceptions import ApplicationError
from app.application.failure_mapping import FailureKind, describe_failure, kind_for_type
from app.presentational.exceptions import AuthenticationError, PresentationError

#: 応答本文へ翻訳できる例外。これ以外は隠さず500として扱う。
TranslatableError = Exception


class FieldError(BaseModel):
    """入力検証で弾かれた項目1件。"""

    #: ``body.name`` のように、本文・パス・クエリの位置を点でつないだもの。
    location: str
    message: str


class ErrorResponse(BaseModel):
    """すべての失敗応答が共有する本文。

    成功以外はこの形1つに揃える。``code`` は安定した識別子でクライアントの分岐に
    使い、``message`` は人が読むためのもので分岐に使わせない。``errors`` は入力
    検証のときだけ埋まるが、キー自体は常に存在させる（有無で形が変わると、結局
    2種類の本文を扱うことになる）。
    """

    code: str
    message: str
    errors: list[FieldError] = []


#: 経路解決の失敗に返す日本語メッセージ。既定は英語なので業務の応答と揃わない。
_ROUTING_MESSAGES: Final[Mapping[HTTPStatus, str]] = {
    HTTPStatus.NOT_FOUND: "指定されたリソースが見つかりません。",
    HTTPStatus.METHOD_NOT_ALLOWED: "このパスでは指定されたメソッドを使用できません。",
}

#: OpenAPI に載せるエラー応答の説明。返しうるステータスは全部ここに要る。
_ERROR_DESCRIPTIONS: Final[Mapping[HTTPStatus, str]] = {
    HTTPStatus.BAD_REQUEST: "HTTP境界でリクエストを解釈できない。",
    HTTPStatus.UNAUTHORIZED: "資格情報が無い、または検証できない。",
    HTTPStatus.FORBIDDEN: "主体は判明したが、その操作の権限が無い。",
    HTTPStatus.NOT_FOUND: "対象が存在しない、または他テナントのため隠されている。",
    HTTPStatus.CONFLICT: "一意制約違反や楽観ロック衝突など、既存の状態と衝突する。",
    HTTPStatus.UNPROCESSABLE_CONTENT: "入力値が形式またはドメイン規則を満たさない。",
}

_STATUS_BY_KIND: Final[Mapping[FailureKind, HTTPStatus]] = {
    FailureKind.INVALID_STATE: HTTPStatus.UNPROCESSABLE_CONTENT,
    FailureKind.UNAUTHENTICATED: HTTPStatus.UNAUTHORIZED,
    FailureKind.FORBIDDEN: HTTPStatus.FORBIDDEN,
    FailureKind.NOT_FOUND: HTTPStatus.NOT_FOUND,
    FailureKind.CONFLICT: HTTPStatus.CONFLICT,
}


def status_for_type(error_type: type[BaseException]) -> HTTPStatus:
    """Applicationの失敗分類をHTTPステータスへ対応させる。"""
    if issubclass(error_type, AuthenticationError):
        return HTTPStatus.UNAUTHORIZED
    if issubclass(error_type, PresentationError):
        return HTTPStatus.BAD_REQUEST
    return _STATUS_BY_KIND[kind_for_type(error_type)]


def status_for(error: Exception) -> HTTPStatus:
    """公開境界の失敗をHTTPステータスへ対応させる。"""
    if isinstance(error, PresentationError):
        return status_for_type(type(error))
    return _STATUS_BY_KIND[describe_failure(error).kind]


def _json(
    status: HTTPStatus,
    body: ErrorResponse,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=int(status),
        content=body.model_dump(),
        headers=dict(headers) if headers else None,
    )


def to_response(error: TranslatableError) -> JSONResponse:
    """例外を共通の応答本文へ変換する。

    例外の型名やスタックは本文へ載せない。内部構造が漏れるうえ、クライアントが
    実装の詳細に依存し始める。分岐に使えるのは安定した ``code`` だけとする。
    """
    public_error = (
        error if isinstance(error, PresentationError) else describe_failure(error)
    )
    return _json(
        status_for(error),
        ErrorResponse(code=public_error.code, message=public_error.message),
    )


async def _translate(request: Request, error: Exception) -> JSONResponse:
    """登録した基底例外を応答へ翻訳する。"""
    del request
    if not isinstance(error, ApplicationError | PresentationError):
        raise error  # pragma: no cover - 登録した型以外は届かない
    return to_response(error)


async def _translate_request_validation(
    request: Request, error: Exception
) -> JSONResponse:
    """入力検証の失敗を、他の失敗と同じ形の本文へ翻訳する。

    FastAPI の既定は ``{"detail": [...]}`` で、ドメイン由来の失敗と形が違う。
    同じ422で本文の形が2種類あると、クライアントは422を見ても分岐を書けない。
    項目ごとの内容は ``errors`` に残すが、封筒は他と揃える。
    """
    del request
    if not isinstance(error, RequestValidationError):
        raise error  # pragma: no cover - 登録した型以外は届かない
    return _json(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorResponse(
            code="REQUEST_VALIDATION_ERROR",
            message="リクエストの内容が正しくありません。",
            # ``loc`` と ``msg`` だけを取り出す。``input`` と ``ctx`` は任意の
            # オブジェクトを含みうるので、そのまま載せるとJSON化で失敗する。
            errors=[
                FieldError(
                    location=".".join(str(part) for part in item["loc"]),
                    message=item["msg"],
                )
                for item in error.errors()
            ],
        ),
    )


async def _translate_http_exception(request: Request, error: Exception) -> JSONResponse:
    """経路解決の失敗（未知のパス・許可されないメソッド）を同じ形へ翻訳する。

    ここを既定のままにすると、存在しないパスだけ ``{"detail": "Not Found"}`` に
    なり、業務の404と形が食い違う。
    """
    del request
    if not isinstance(error, StarletteHTTPException):
        raise error  # pragma: no cover - 登録した型以外は届かない
    status = HTTPStatus(error.status_code)
    return _json(
        status,
        ErrorResponse(
            code=status.name,
            message=_ROUTING_MESSAGES.get(status, str(error.detail)),
        ),
        # 405 の ``Allow`` のように、ステータスと対になるヘッダを落とさない。
        headers=error.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """ApplicationとPresentationの基底例外、およびHTTP入力の失敗を登録する。

    Domain例外はApplicationの公開境界で変換してからここへ渡す。"""
    for base in (ApplicationError, PresentationError):
        app.add_exception_handler(base, _translate)
    app.add_exception_handler(RequestValidationError, _translate_request_validation)
    app.add_exception_handler(StarletteHTTPException, _translate_http_exception)


def error_responses(*statuses: HTTPStatus) -> dict[int | str, dict[str, Any]]:
    """OpenAPI へ載せるエラー応答の定義を作る。

    実際に返すステータスをスキーマへ書かないと、生成クライアントはエラーを型と
    して扱えず、成功応答だけを知ることになる。説明の無いステータスを渡すと
    ``KeyError`` で落ちるので、返しうるステータスと説明の対応は常に揃う。
    """
    return {
        int(status): {
            "model": ErrorResponse,
            "description": _ERROR_DESCRIPTIONS[status],
        }
        for status in statuses
    }


__all__ = [
    "ErrorResponse",
    "FieldError",
    "TranslatableError",
    "error_responses",
    "register_error_handlers",
    "status_for",
    "status_for_type",
    "to_response",
]
