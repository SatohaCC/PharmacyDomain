"""法人コンテキストのHTTPルート。

登録と状態変更はベンダーシステム管理者専用だが、その判定はここでは行わない。
権限はユースケースが ``Permission`` で要求し、``AuthorizationService`` が判定する。
ルータ側で先回りして弾くと、判定が2箇所になって片方だけ緩む。
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from app.application.corporate import (
    ChangeCorporateNameCommand,
    ChangeCorporateStatusCommand,
    ChangeRepresentativeCommand,
    CorporateResponseDto,
    RegisterCorporateCommand,
)
from app.presentational.dependencies import CorporateUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RegisteredIdResponse, RequestModel

router = APIRouter(
    prefix="/corporates",
    tags=["corporate"],
    # ルータ単位で認証を要求する。ルート関数の引数に頼ると、新しいルートを
    # 足したときに書き忘れた1本だけが無認証で公開される。
    dependencies=[Depends(get_actor_context)],
    # 認証・認可・入力検証はどのルートでも起こる。ルータ単位で書いておくと、
    # ルートを足したときに書き漏らさない。
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterCorporateRequest(RequestModel):
    """法人登録の入力。"""

    name: str
    representative_last_name: str
    representative_first_name: str


class ChangeCorporateNameRequest(RequestModel):
    """法人名変更の入力。"""

    name: str


class ChangeRepresentativeRequest(RequestModel):
    """代表者名変更の入力。"""

    last_name: str
    first_name: str


class ChangeCorporateStatusRequest(RequestModel):
    """法人の利用状態変更の入力。"""

    is_active: bool


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=RegisteredIdResponse,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_corporate(
    body: RegisterCorporateRequest,
    use_cases: CorporateUseCasesDep,
) -> RegisteredIdResponse:
    """法人を新規登録する。"""
    corporate_id = await use_cases.register.execute(
        RegisterCorporateCommand(
            name=body.name,
            representative_last_name=body.representative_last_name,
            representative_first_name=body.representative_first_name,
        )
    )
    return RegisteredIdResponse(id=str(corporate_id.value))


@router.get(
    "/{corporate_id}",
    response_model=CorporateResponseDto,
    responses=error_responses(HTTPStatus.NOT_FOUND),
)
async def get_corporate(
    corporate_id: str,
    use_cases: CorporateUseCasesDep,
) -> CorporateResponseDto:
    """法人を1件取得する。"""
    return await use_cases.get.execute(corporate_id)


@router.patch(
    "/{corporate_id}/name",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT),
)
async def change_corporate_name(
    corporate_id: str,
    body: ChangeCorporateNameRequest,
    use_cases: CorporateUseCasesDep,
) -> None:
    """法人名を変更する。"""
    await use_cases.change_name.execute(
        ChangeCorporateNameCommand(corporate_id=corporate_id, new_name=body.name)
    )


@router.patch(
    "/{corporate_id}/representative",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT),
)
async def change_representative(
    corporate_id: str,
    body: ChangeRepresentativeRequest,
    use_cases: CorporateUseCasesDep,
) -> None:
    """代表者名を変更する。"""
    await use_cases.change_representative.execute(
        ChangeRepresentativeCommand(
            corporate_id=corporate_id,
            new_last_name=body.last_name,
            new_first_name=body.first_name,
        )
    )


@router.patch(
    "/{corporate_id}/status",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT),
)
async def change_corporate_status(
    corporate_id: str,
    body: ChangeCorporateStatusRequest,
    use_cases: CorporateUseCasesDep,
) -> None:
    """法人の利用状態を変更する（ベンダーシステム管理者専用）。"""
    await use_cases.change_status.execute(
        ChangeCorporateStatusCommand(
            corporate_id=corporate_id,
            is_active=body.is_active,
        )
    )


__all__ = ["router"]
