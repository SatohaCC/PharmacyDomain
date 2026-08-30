"""店舗コンテキストのHTTPルート。

法人IDはパスに置く。ボディへ置くと、同じ操作が「パスの法人」と「ボディの法人」
の2つを名乗れてしまい、テナント境界の検証対象がどちらか曖昧になる。
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from app.application.store import (
    ChangeInsurancePharmacyNumberCommand,
    ChangeStoreAddressCommand,
    ChangeStoreCodeCommand,
    ChangeStoreContactInfoCommand,
    ChangeStoreNamesCommand,
    GetStoreQuery,
    ListStoresQuery,
    RegisterStoreCommand,
    StoreDto,
    StoreSummaryDto,
)
from app.presentational.dependencies import StoreUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RegisteredIdResponse, RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}/stores",
    tags=["store"],
    dependencies=[Depends(get_actor_context)],
    # 404 もルータ単位に置く。全ルートが親法人をパスに持つので、法人が無い・
    # 他テナントである場合はどのルートでも404になる。
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterStoreRequest(RequestModel):
    """店舗登録の入力。"""

    name: str
    name_kana: str
    postal_code: str
    address: str
    phone_number: str
    name_romaji: str | None = None
    fax_number: str | None = None
    email: str | None = None
    code: str | None = None
    insurance_pharmacy_number: str | None = None


class ChangeStoreNamesRequest(RequestModel):
    """店舗名変更の入力。"""

    name: str
    name_kana: str
    name_romaji: str | None = None


class ChangeStoreCodeRequest(RequestModel):
    """店舗コード変更の入力。``None``・空文字・空白はいずれも解除を意味する。"""

    code: str | None = None


class ChangeStoreAddressRequest(RequestModel):
    """店舗所在地変更の入力。"""

    postal_code: str
    address: str


class ChangeStoreContactInfoRequest(RequestModel):
    """店舗連絡先変更の入力。"""

    phone_number: str
    fax_number: str | None = None
    email: str | None = None


class ChangeInsurancePharmacyNumberRequest(RequestModel):
    """保険薬局指定番号変更の入力。``None``・空文字・空白はいずれも解除を意味する。"""

    insurance_pharmacy_number: str | None = None


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=RegisteredIdResponse,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_store(
    corporate_id: str,
    body: RegisterStoreRequest,
    use_cases: StoreUseCasesDep,
) -> RegisteredIdResponse:
    """店舗を新規登録する。"""
    store_id = await use_cases.register.execute(
        RegisterStoreCommand(
            corporate_id=corporate_id,
            name=body.name,
            name_kana=body.name_kana,
            postal_code=body.postal_code,
            address=body.address,
            phone_number=body.phone_number,
            name_romaji=body.name_romaji,
            fax_number=body.fax_number,
            email=body.email,
            code=body.code,
            insurance_pharmacy_number=body.insurance_pharmacy_number,
        )
    )
    return RegisteredIdResponse(id=str(store_id.value))


@router.get("", response_model=list[StoreSummaryDto])
async def list_stores(
    corporate_id: str,
    use_cases: StoreUseCasesDep,
) -> list[StoreSummaryDto]:
    """法人に所属する店舗を一覧する。"""
    return await use_cases.list_by_corporate.execute(
        ListStoresQuery(corporate_id=corporate_id)
    )


@router.get("/{store_id}", response_model=StoreDto)
async def get_store(
    corporate_id: str,
    store_id: str,
    use_cases: StoreUseCasesDep,
) -> StoreDto:
    """店舗を1件取得する。"""
    return await use_cases.get.execute(
        GetStoreQuery(corporate_id=corporate_id, store_id=store_id)
    )


@router.patch(
    "/{store_id}/names",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_store_names(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreNamesRequest,
    use_cases: StoreUseCasesDep,
) -> None:
    """店舗名を変更する。"""
    await use_cases.change_names.execute(
        ChangeStoreNamesCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            new_name=body.name,
            new_name_kana=body.name_kana,
            new_romaji=body.name_romaji,
        )
    )


@router.patch(
    "/{store_id}/code",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_store_code(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreCodeRequest,
    use_cases: StoreUseCasesDep,
) -> None:
    """店舗コードを変更または解除する。"""
    await use_cases.change_code.execute(
        ChangeStoreCodeCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            new_code=body.code,
        )
    )


@router.patch(
    "/{store_id}/address",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_store_address(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreAddressRequest,
    use_cases: StoreUseCasesDep,
) -> None:
    """店舗所在地を変更する。"""
    await use_cases.change_address.execute(
        ChangeStoreAddressCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            postal_code=body.postal_code,
            address=body.address,
        )
    )


@router.patch(
    "/{store_id}/contact-info",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_store_contact_info(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreContactInfoRequest,
    use_cases: StoreUseCasesDep,
) -> None:
    """店舗連絡先を変更する。"""
    await use_cases.change_contact_info.execute(
        ChangeStoreContactInfoCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            phone_number=body.phone_number,
            fax_number=body.fax_number,
            email=body.email,
        )
    )


@router.patch(
    "/{store_id}/insurance-pharmacy-number",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_insurance_pharmacy_number(
    corporate_id: str,
    store_id: str,
    body: ChangeInsurancePharmacyNumberRequest,
    use_cases: StoreUseCasesDep,
) -> None:
    """保険薬局指定番号を変更または解除する。"""
    await use_cases.change_insurance_pharmacy_number.execute(
        ChangeInsurancePharmacyNumberCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            new_number=body.insurance_pharmacy_number,
        )
    )


__all__ = ["router"]
