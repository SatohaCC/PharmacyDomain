"""店舗コンテキストのHTTPルート。

法人IDはパスに置く。ボディへ置くと、同じ操作が「パスの法人」と「ボディの法人」
の2つを名乗れてしまい、テナント境界の検証対象がどちらか曖昧になる。
"""

from __future__ import annotations

from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.application.common.pagination import Page
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
from app.application.store.business_hours import (
    BusinessDayExceptionInput,
    BusinessHoursDto,
    ChangeStoreBusinessHoursCommand,
    StoreOpeningStatusDto,
    StoreOpeningStatusQuery,
    WeekdayBusinessHoursInput,
)
from app.application.store.get_store import StoreStatusChangeDto
from app.application.store.management import (
    ChangeStoreStatusCommand,
    ManagerAction,
    ManagerAssignmentDto,
    ManageStoreManagerCommand,
    RevokeStoreClosureCommand,
)
from app.domain.store.lifecycle import StoreStatus
from app.presentational.dependencies import StoreUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RegisteredIdResponse, RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}/stores",
    tags=["store"],
    dependencies=[Depends(get_actor_context)],
    # 404 もルータ単位に置く。全ルートが親法人をパスに持つので、法人が無い・
    # 他テナントである場合はどのルートでも404になる。409 も同じ理由で置く。
    # 書き込みは一意制約違反だけでなく楽観ロック衝突でも409になるため、ルートごとに
    # 書き足す運用にすると、新しく足した1本だけが宣言を欠く。
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
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


class ChangeStoreStatusRequest(RequestModel):
    """状態変更理由。操作者・日時は入力しない。"""

    reason: str


@router.post(
    "/{store_id}/suspension",
    response_model=StoreDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def suspend_store(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreStatusRequest,
    use_cases: StoreUseCasesDep,
) -> StoreDto:
    """店舗を休止する。"""
    return await use_cases.change_status.execute(
        ChangeStoreStatusCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            status=StoreStatus.SUSPENDED,
            reason=body.reason,
        )
    )


@router.post(
    "/{store_id}/resumption",
    response_model=StoreDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def resume_store(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreStatusRequest,
    use_cases: StoreUseCasesDep,
) -> StoreDto:
    """休止した店舗を再開する。"""
    return await use_cases.change_status.execute(
        ChangeStoreStatusCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            status=StoreStatus.ACTIVE,
            reason=body.reason,
        )
    )


@router.post(
    "/{store_id}/closure",
    response_model=StoreDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def close_store(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreStatusRequest,
    use_cases: StoreUseCasesDep,
) -> StoreDto:
    """残業務を確認して店舗を閉局する。"""
    return await use_cases.change_status.execute(
        ChangeStoreStatusCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            status=StoreStatus.CLOSED,
            reason=body.reason,
        )
    )


@router.post(
    "/{store_id}/closure-revocation",
    response_model=StoreDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def revoke_store_closure(
    corporate_id: str,
    store_id: str,
    body: ChangeStoreStatusRequest,
    use_cases: StoreUseCasesDep,
) -> StoreDto:
    """誤って登録された閉局を取り消し、休止へ戻す（ベンダー専用）。

    閉局と対称な「再開」にはしない。閉局で管理薬剤師の任命は終了しているので、
    有効へ戻すと管理薬剤師のいない店舗が業務を受けられる状態になる。
    """
    return await use_cases.revoke_closure.execute(
        RevokeStoreClosureCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            reason=body.reason,
        )
    )


class ChangeBusinessHoursRequest(RequestModel):
    """開局時間の一括置き換え。曜日は7つすべてを指定する。

    入れ子はApplication層の入力DTOをそのまま型に置く。ここで写し取ると、
    項目が増えたときに黙って落ちる項目ができる。
    """

    weekly: tuple[WeekdayBusinessHoursInput, ...]
    exceptions: tuple[BusinessDayExceptionInput, ...] = ()


@router.put(
    "/{store_id}/business-hours",
    response_model=BusinessHoursDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_business_hours(
    corporate_id: str,
    store_id: str,
    body: ChangeBusinessHoursRequest,
    use_cases: StoreUseCasesDep,
) -> BusinessHoursDto:
    """開局時間をまとめて置き換える。

    部分更新にしない。週次の予定は全曜日が揃って初めて意味を持つので、曜日を
    1つだけ差し替えられると、残りの曜日がいつ登録されたものか分からなくなる。
    """
    return await use_cases.change_business_hours.execute(
        ChangeStoreBusinessHoursCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            weekly=body.weekly,
            exceptions=body.exceptions,
        )
    )


@router.get("/{store_id}/opening-status", response_model=StoreOpeningStatusDto)
async def get_opening_status(
    corporate_id: str,
    store_id: str,
    use_cases: StoreUseCasesDep,
    at: Annotated[
        datetime | None,
        Query(description="判定する日時。タイムゾーンが必要。省略時は現在。"),
    ] = None,
) -> StoreOpeningStatusDto:
    """指定日時に開局しているかを返す。

    未登録は「開いている」にも「閉じている」にも倒さず ``unknown`` を返す。
    """
    return await use_cases.opening_status.execute(
        StoreOpeningStatusQuery(corporate_id=corporate_id, store_id=store_id, at=at)
    )


@router.get("/{store_id}/status-history", response_model=list[StoreStatusChangeDto])
async def get_status_history(
    corporate_id: str, store_id: str, use_cases: StoreUseCasesDep
) -> list[StoreStatusChangeDto]:
    """店舗状態の履歴を取得する。"""
    store = await use_cases.get.execute(
        GetStoreQuery(corporate_id=corporate_id, store_id=store_id)
    )
    return list(store.status_history)


class ManageManagerRequest(RequestModel):
    """管理薬剤師の任命履歴への操作。"""

    action: ManagerAction = ManagerAction.APPOINT
    assignment_id: str | None = None
    staff_id: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None


@router.post(
    "/{store_id}/manager-assignments",
    response_model=ManagerAssignmentDto,
)
async def manage_manager(
    corporate_id: str,
    store_id: str,
    body: ManageManagerRequest,
    use_cases: StoreUseCasesDep,
) -> ManagerAssignmentDto:
    """管理薬剤師を任命・交代・取消・終了する。"""
    return await use_cases.manage_manager.execute(
        ManageStoreManagerCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            action=body.action,
            assignment_id=body.assignment_id,
            staff_id=body.staff_id,
            starts_on=body.starts_on,
            ends_on=body.ends_on,
        )
    )


class EndManagerRequest(RequestModel):
    """任命の終了日。"""

    ends_on: date


class ReplaceManagerRequest(RequestModel):
    """管理薬剤師交代の入力。"""

    current_assignment_id: str
    new_staff_id: str
    effective_on: date


@router.get("/{store_id}/manager-assignments")
async def list_managers(
    corporate_id: str,
    store_id: str,
    use_cases: StoreUseCasesDep,
    as_of: date | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> Page[ManagerAssignmentDto]:
    """指定日の管理薬剤師または任命履歴を取得する。"""
    return await use_cases.manage_manager.list_assignments(
        corporate_id, store_id, as_of=as_of, after=cursor, limit=limit
    )


@router.post(
    "/{store_id}/manager-assignments/{assignment_id}/ending",
    response_model=ManagerAssignmentDto,
)
async def end_manager(
    corporate_id: str,
    store_id: str,
    assignment_id: str,
    body: EndManagerRequest,
    use_cases: StoreUseCasesDep,
) -> ManagerAssignmentDto:
    """管理薬剤師の任命期間を終了する。"""
    return await use_cases.manage_manager.execute(
        ManageStoreManagerCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            assignment_id=assignment_id,
            action=ManagerAction.END,
            ends_on=body.ends_on,
        )
    )


@router.post(
    "/{store_id}/manager-assignments/{assignment_id}/cancellation",
    response_model=ManagerAssignmentDto,
)
async def cancel_manager(
    corporate_id: str, store_id: str, assignment_id: str, use_cases: StoreUseCasesDep
) -> ManagerAssignmentDto:
    """開始前の任命を取消し履歴を残す。"""
    return await use_cases.manage_manager.execute(
        ManageStoreManagerCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            assignment_id=assignment_id,
            action=ManagerAction.CANCEL,
        )
    )


@router.post("/{store_id}/manager-replacement", response_model=ManagerAssignmentDto)
async def replace_manager(
    corporate_id: str,
    store_id: str,
    body: ReplaceManagerRequest,
    use_cases: StoreUseCasesDep,
) -> ManagerAssignmentDto:
    """旧任命の終了と新任命を同時に確定する。"""
    return await use_cases.manage_manager.execute(
        ManageStoreManagerCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            assignment_id=body.current_assignment_id,
            staff_id=body.new_staff_id,
            action=ManagerAction.REPLACE,
            starts_on=body.effective_on,
        )
    )


__all__ = ["router"]
