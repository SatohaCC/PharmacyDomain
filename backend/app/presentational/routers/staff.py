"""スタッフコンテキストのHTTPルート。

退職と有効化は対称ではないので、1つの状態フラグにまとめない。退職は退職日を
取って所属履歴を打ち切るが、有効化は所属を復元しない。``PATCH /status`` の
ような形にすると、この非対称が本文の真偽値に隠れてしまう。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field

from app.application.staff.commands.activate_staff import ActivateStaffCommand
from app.application.staff.commands.assign_staff_concurrent_store import (
    AssignStaffConcurrentStoreCommand,
)
from app.application.staff.commands.change_staff_job_title import (
    ChangeStaffJobTitleCommand,
)
from app.application.staff.commands.change_staff_names import ChangeStaffNamesCommand
from app.application.staff.commands.deactivate_staff import DeactivateStaffCommand
from app.application.staff.commands.manage_staff_leave import (
    ReturnStaffFromLeaveCommand,
    StartStaffLeaveCommand,
)
from app.application.staff.commands.register_staff import (
    BulkStaffAccountInput,
    RegisterStaffCommand,
)
from app.application.staff.commands.remove_staff_concurrent_store import (
    RemoveStaffConcurrentStoreCommand,
)
from app.application.staff.commands.transfer_staff_home_store import (
    TransferStaffHomeStoreCommand,
)
from app.application.staff.commands.update_staff_employment import (
    UpdateStaffEmploymentCommand,
)
from app.application.staff.commands.update_staff_qualifications import (
    UpdateStaffQualificationsCommand,
)
from app.application.staff.queries.dtos.get_staff import StaffDto
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.models import GetStaffQuery, ListStaffsQuery
from app.presentational.dependencies import StaffUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.routing import ApplicationRoute
from app.presentational.schemas import RequestModel

router = APIRouter(
    route_class=ApplicationRoute,
    prefix="/corporates/{corporate_id}/staffs",
    tags=["staff"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class QualificationsRequest(RequestModel):
    """資格の入力。項目を省くと、その資格を持たないものとして上書きする。"""

    pharmacist_license_number: str | None = None
    insurance_pharmacist_registration_number: str | None = None
    insurance_pharmacist_registration_date: date | None = None
    registered_seller_number: str | None = None
    dietitian_registration_number: str | None = None
    is_registered_dietitian: bool = True


class StaffAccountRequest(RequestModel):
    """スタッフと同時に生成するアカウントの入力。"""

    email: str = Field(max_length=256)
    password: str = Field(repr=False, min_length=15, max_length=128)
    role: str = "store_operator"
    store_ids: tuple[str, ...] | None = None


class RegisterStaffRequest(QualificationsRequest):
    """スタッフ登録の入力。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    account: StaffAccountRequest
    job_title: str | None = None
    code: str | None = None
    phone_number: str | None = None
    email: str | None = None
    initial_home_store_id: str | None = None
    initial_start_date: date | None = None
    employment_type: str = "regular"
    weekly_contract_hours: float | None = None


class BulkRegisteredStaffResponse(RequestModel):
    """スタッフ一括登録の応答。"""

    id: str
    staff_id: str
    person_id: str
    account_id: str
    membership_id: str
    email: str


class ChangeStaffNamesRequest(RequestModel):
    """氏名変更の入力。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class ChangeStaffJobTitleRequest(RequestModel):
    """役職変更の入力。``None``・空文字・空白はいずれも解除を意味する。"""

    job_title: str | None = None


class TransferHomeStoreRequest(RequestModel):
    """主所属の異動の入力。"""

    store_id: str
    transfer_date: date


class AssignConcurrentStoreRequest(RequestModel):
    """兼務の追加の入力。"""

    store_id: str
    start_date: date


class UpdateStaffEmploymentRequest(RequestModel):
    """スタッフ労働契約変更の入力モデル。"""

    employment_type: str
    weekly_contract_hours: float | None = None


class StartStaffLeaveRequest(RequestModel):
    """スタッフ休職開始の入力モデル。"""

    leave_reason: str
    left_on: date


class RetireStaffRequest(RequestModel):
    """退職の入力。退職日以降に及ぶ所属はこの日で打ち切られる。"""

    retired_on: date


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=BulkRegisteredStaffResponse,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_staff(
    corporate_id: str,
    body: RegisterStaffRequest,
    use_cases: StaffUseCasesDep,
) -> BulkRegisteredStaffResponse:
    """スタッフおよびアカウントを新規一括登録する。"""
    result = await use_cases.register.execute(
        RegisterStaffCommand(
            corporate_id=corporate_id,
            last_name=body.last_name,
            first_name=body.first_name,
            last_name_kana=body.last_name_kana,
            first_name_kana=body.first_name_kana,
            account=BulkStaffAccountInput(
                email=body.account.email,
                password=body.account.password,
                role=body.account.role,
                store_ids=body.account.store_ids,
            ),
            job_title=body.job_title,
            code=body.code,
            phone_number=body.phone_number,
            email=body.email,
            initial_home_store_id=body.initial_home_store_id,
            initial_start_date=body.initial_start_date,
            pharmacist_license_number=body.pharmacist_license_number,
            insurance_pharmacist_registration_number=(
                body.insurance_pharmacist_registration_number
            ),
            insurance_pharmacist_registration_date=(
                body.insurance_pharmacist_registration_date
            ),
            registered_seller_number=body.registered_seller_number,
            dietitian_registration_number=body.dietitian_registration_number,
            is_registered_dietitian=body.is_registered_dietitian,
            employment_type=body.employment_type,
            weekly_contract_hours=body.weekly_contract_hours,
        )
    )
    return BulkRegisteredStaffResponse(
        id=result.staff_id,
        staff_id=result.staff_id,
        person_id=result.person_id,
        account_id=result.account_id,
        membership_id=result.membership_id,
        email=result.email,
    )


@router.get("", response_model=list[StaffSummaryDto])
async def list_staffs(
    corporate_id: str,
    use_cases: StaffUseCasesDep,
) -> list[StaffSummaryDto]:
    """法人に所属するスタッフを一覧する。"""
    return await use_cases.list_by_corporate.execute(
        ListStaffsQuery(corporate_id=corporate_id)
    )


@router.get("/{staff_id}", response_model=StaffDto | StaffSummaryDto)
async def get_staff(
    corporate_id: str,
    staff_id: str,
    use_cases: StaffUseCasesDep,
    target_date: Annotated[
        date | None,
        Query(description="所属の判定に使う適用日。省略すると所属は空として扱う。"),
    ] = None,
) -> StaffDto | StaffSummaryDto:
    """スタッフを1件取得する。"""
    return await use_cases.get.execute(
        GetStaffQuery(
            corporate_id=corporate_id, staff_id=staff_id, target_date=target_date
        )
    )


@router.patch(
    "/{staff_id}/names",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_staff_names(
    corporate_id: str,
    staff_id: str,
    body: ChangeStaffNamesRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """氏名を変更する。"""
    await use_cases.change_names.execute(
        ChangeStaffNamesCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            last_name=body.last_name,
            first_name=body.first_name,
            last_name_kana=body.last_name_kana,
            first_name_kana=body.first_name_kana,
        )
    )


@router.patch(
    "/{staff_id}/job-title",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_staff_job_title(
    corporate_id: str,
    staff_id: str,
    body: ChangeStaffJobTitleRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """役職を変更または解除する。"""
    await use_cases.change_job_title.execute(
        ChangeStaffJobTitleCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            job_title=body.job_title,
        )
    )


@router.put(
    "/{staff_id}/qualifications",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def update_staff_qualifications(
    corporate_id: str,
    staff_id: str,
    body: QualificationsRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """資格を差し替える。

    PATCH ではなく PUT なのは、送られた内容で資格一式を置き換えるからである。
    省いた項目は「変更しない」ではなく「その資格を持たない」になる。
    """
    await use_cases.update_qualifications.execute(
        UpdateStaffQualificationsCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            pharmacist_license_number=body.pharmacist_license_number,
            insurance_pharmacist_registration_number=(
                body.insurance_pharmacist_registration_number
            ),
            insurance_pharmacist_registration_date=(
                body.insurance_pharmacist_registration_date
            ),
            registered_seller_number=body.registered_seller_number,
            dietitian_registration_number=body.dietitian_registration_number,
            is_registered_dietitian=body.is_registered_dietitian,
        )
    )


@router.patch(
    "/{staff_id}/home-store",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def transfer_home_store(
    corporate_id: str,
    staff_id: str,
    body: TransferHomeStoreRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """主所属店舗を異動する。"""
    await use_cases.transfer_home_store.execute(
        TransferStaffHomeStoreCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            new_store_id=body.store_id,
            transfer_date=body.transfer_date,
        )
    )


@router.post(
    "/{staff_id}/concurrent-stores",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def assign_concurrent_store(
    corporate_id: str,
    staff_id: str,
    body: AssignConcurrentStoreRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """兼務店舗を追加する。"""
    await use_cases.assign_concurrent_store.execute(
        AssignStaffConcurrentStoreCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            store_id=body.store_id,
            start_date=body.start_date,
        )
    )


@router.delete(
    "/{staff_id}/concurrent-stores/{store_id}",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def remove_concurrent_store(
    corporate_id: str,
    staff_id: str,
    store_id: str,
    use_cases: StaffUseCasesDep,
    end_date: Annotated[
        date, Query(description="兼務を終了する日。この日までは在籍とする。")
    ],
) -> None:
    """兼務店舗の期間を終了する。

    終了日をクエリで受け取る。本文つきの ``DELETE`` は経路によって落とされる
    ことがあり、期間の指定が黙って消える。
    """
    await use_cases.remove_concurrent_store.execute(
        RemoveStaffConcurrentStoreCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            store_id=store_id,
            end_date=end_date,
        )
    )


@router.post(
    "/{staff_id}/retirement",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def retire_staff(
    corporate_id: str,
    staff_id: str,
    body: RetireStaffRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """退職させ、退職日以降に及ぶ所属をその日で打ち切る。"""
    await use_cases.deactivate.execute(
        DeactivateStaffCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            retired_on=body.retired_on,
        )
    )


@router.post(
    "/{staff_id}/reactivation",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def reactivate_staff(
    corporate_id: str,
    staff_id: str,
    use_cases: StaffUseCasesDep,
) -> None:
    """在籍状態へ戻す。**所属は復元しない**ので、必要なら別途配属する。"""
    await use_cases.activate.execute(
        ActivateStaffCommand(corporate_id=corporate_id, staff_id=staff_id)
    )


@router.patch(
    "/{staff_id}/employment",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def update_staff_employment(
    corporate_id: str,
    staff_id: str,
    body: UpdateStaffEmploymentRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """スタッフの雇用形態・週所定労働時間を更新する。"""
    await use_cases.update_employment.execute(
        UpdateStaffEmploymentCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            employment_type=body.employment_type,
            weekly_contract_hours=body.weekly_contract_hours,
        )
    )


@router.post(
    "/{staff_id}/leave",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def start_staff_leave(
    corporate_id: str,
    staff_id: str,
    body: StartStaffLeaveRequest,
    use_cases: StaffUseCasesDep,
) -> None:
    """スタッフの休職を開始する。"""
    await use_cases.start_leave.execute(
        StartStaffLeaveCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
            leave_reason=body.leave_reason,
            left_on=body.left_on,
        )
    )


@router.post(
    "/{staff_id}/return-from-leave",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def return_staff_from_leave(
    corporate_id: str,
    staff_id: str,
    use_cases: StaffUseCasesDep,
) -> None:
    """スタッフを休職から復職させる。"""
    await use_cases.return_from_leave.execute(
        ReturnStaffFromLeaveCommand(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
    )


__all__ = ["router"]
