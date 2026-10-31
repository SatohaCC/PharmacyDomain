"""個人のアカウントと法人アクセス権のHTTP窓口。"""

from datetime import date
from http import HTTPStatus

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.common.pagination import Page
from app.application.composition.commands.register_contract import (
    RegisterContractCommand,
    RegisteredContract,
)
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.commands.dtos.identity_views import CurrentActorDto
from app.application.identity.commands.models import (
    AccountStatus,
    MembershipRole,
    PersonNamesInput,
)
from app.application.identity.commands.register_staff_for_admin import (
    RegisterStaffForAdminCommand,
)
from app.application.identity.queries.dtos.identity_views import (
    MembershipViewDto,
    SelectableStoreDto,
)
from app.presentational.dependencies import (
    Actor,
    IdentityUseCasesDep,
    get_actor_context,
)
from app.presentational.errors import error_responses
from app.presentational.exceptions import AuthenticationError
from app.presentational.routing import ApplicationRoute
from app.presentational.schemas import RegisteredIdResponse, RequestModel

#: 通常のIdentity操作。認証はルータ単位で掛ける。
#:
#: ルート関数の引数に頼ると、新しいルートを足したときに書き忘れた1本だけが
#: 無認証で公開される。アカウントと法人アクセス権を扱うルータで、それは最も
#: 起きてはいけない漏れ方をする。
router = APIRouter(
    route_class=ApplicationRoute,
    tags=["identity"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterContractRequest(RequestModel):
    """新規契約の法人と初期管理者を一括登録する入力。"""

    name: str
    representative_last_name: str
    representative_first_name: str
    administrator: PersonNamesInput
    email: str = Field(max_length=256)
    initial_password: str = Field(repr=False, min_length=15, max_length=128)


@router.post("/contracts", status_code=201, response_model=RegisteredContract)
async def register_contract(
    body: RegisterContractRequest, use_cases: IdentityUseCasesDep
) -> RegisteredContract:
    """ベンダーが法人・初期管理者・資格情報を一括登録する。"""
    return await use_cases.register_contract.execute(
        RegisterContractCommand(
            name=body.name,
            representative_last_name=body.representative_last_name,
            representative_first_name=body.representative_first_name,
            administrator=body.administrator,
            email=body.email,
            initial_password=body.initial_password,
        )
    )


class ChangeMembershipRequest(RequestModel):
    """同じ本人・アカウントの法人アクセス権の変更。"""

    status: AccountStatus | None = None
    role: MembershipRole | None = None
    store_ids: tuple[str, ...] | None = None
    store_id: str | None = None
    store_is_active: bool | None = None


@router.patch(
    "/corporates/{corporate_id}/users/{membership_id}",
    response_model=RegisteredIdResponse,
)
async def change_membership(
    corporate_id: str,
    membership_id: str,
    body: ChangeMembershipRequest,
    use_cases: IdentityUseCasesDep,
) -> RegisteredIdResponse:
    """法人アクセス権を変更する。個人アカウントの所有者は変えない。"""
    membership = await use_cases.change_membership.execute(
        corporate_id,
        membership_id,
        status=body.status,
        role=body.role,
        store_ids=body.store_ids,
        store_id=body.store_id,
        store_is_active=body.store_is_active,
    )
    return RegisteredIdResponse(id=str(membership.id.value))


@router.post(
    "/accounts/{account_id}/suspension",
    response_model=RegisteredIdResponse,
)
async def suspend_account(
    account_id: str, use_cases: IdentityUseCasesDep
) -> RegisteredIdResponse:
    """ベンダーまたは自法人の管理者が個人アカウント全体を停止する。"""
    account = await use_cases.suspend_account.execute(account_id)
    return RegisteredIdResponse(id=str(account.id.value))


@router.get("/me")
async def get_me(actor: Actor, use_cases: IdentityUseCasesDep) -> CurrentActorDto:
    """現在有効な本人・アカウント・法人アクセス範囲を返す。"""
    if not isinstance(actor, ResolvedActorContext):
        raise AuthenticationError("本人を特定できません。")
    current = await use_cases.resolve_actor.execute(
        VerifiedSubject(
            principal_id=actor.principal_id,
            selected_store_id=str(actor.selected_store_id.value)
            if actor.selected_store_id is not None
            else None,
        )
    )
    return CurrentActorDto.from_actor(current)


@router.get("/me/stores")
async def get_my_stores(
    actor: Actor, use_cases: IdentityUseCasesDep
) -> tuple[SelectableStoreDto, ...]:
    """現在選択可能な店舗一覧（有効Membership許可店舗と当日Staff所属の積集合）を返す。"""
    if not isinstance(actor, ResolvedActorContext):
        raise AuthenticationError("本人を特定できません。")
    return await use_cases.resolve_actor.list_selectable_stores(
        VerifiedSubject(principal_id=actor.principal_id)
    )


class RegisterPersonRequest(RequestModel):
    """自法人の本人を登録する。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class LinkPersonRequest(RequestModel):
    """既存本人との明示的な対応。氏名推測はしない。"""

    person_id: str


@router.get("/corporates/{corporate_id}/users")
async def list_users(
    corporate_id: str,
    use_cases: IdentityUseCasesDep,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> Page[MembershipViewDto]:
    """自法人のユーザー権限を一覧する。"""
    return await use_cases.list_users.execute(corporate_id, after=cursor, limit=limit)


@router.get(
    "/corporates/{corporate_id}/users/{membership_id}",
)
async def get_user(
    corporate_id: str, membership_id: str, use_cases: IdentityUseCasesDep
) -> MembershipViewDto:
    """自法人のユーザー権限を取得する。"""
    return await use_cases.get_user.execute(corporate_id, membership_id)


@router.post(
    "/corporates/{corporate_id}/users/{membership_id}/suspension",
)
async def suspend_membership(
    corporate_id: str,
    membership_id: str,
    use_cases: IdentityUseCasesDep,
) -> RegisteredIdResponse:
    """法人のアクセス権だけを停止する。"""
    membership = await use_cases.change_membership.execute(
        corporate_id, membership_id, status=AccountStatus.SUSPENDED
    )
    return RegisteredIdResponse(id=str(membership.id.value))


@router.post(
    "/corporates/{corporate_id}/users/{membership_id}/reactivation",
)
async def reactivate_membership(
    corporate_id: str,
    membership_id: str,
    use_cases: IdentityUseCasesDep,
) -> RegisteredIdResponse:
    """本人・スタッフの有効性を再確認して権限を再開する。"""
    membership = await use_cases.change_membership.execute(
        corporate_id, membership_id, status=AccountStatus.ACTIVE
    )
    return RegisteredIdResponse(id=str(membership.id.value))


class RegisterStaffForAdminRequest(RequestModel):
    """初期管理者へのスタッフ登録入力。"""

    last_name: str | None = None
    first_name: str | None = None
    last_name_kana: str | None = None
    first_name_kana: str | None = None
    code: str | None = None
    job_title: str | None = None
    phone_number: str | None = None
    email: str | None = None
    initial_home_store_id: str | None = None
    initial_start_date: date | None = None
    pharmacist_license_number: str | None = None
    insurance_pharmacist_registration_number: str | None = None
    insurance_pharmacist_registration_date: date | None = None
    registered_seller_number: str | None = None
    dietitian_registration_number: str | None = None
    is_registered_dietitian: bool = True


@router.post(
    "/corporates/{corporate_id}/users/{membership_id}/staff-registration",
    response_model=RegisteredIdResponse,
    status_code=HTTPStatus.CREATED,
)
async def register_staff_for_admin(
    corporate_id: str,
    membership_id: str,
    body: RegisterStaffForAdminRequest,
    use_cases: IdentityUseCasesDep,
) -> RegisteredIdResponse:
    """初期管理者にスタッフを紐付ける。"""
    staff_id = await use_cases.register_staff_for_admin.execute(
        RegisterStaffForAdminCommand(
            corporate_id=corporate_id,
            membership_id=membership_id,
            **body.model_dump(),
        )
    )
    return RegisteredIdResponse(id=str(staff_id.value))


@router.post(
    "/corporates/{corporate_id}/people",
    status_code=HTTPStatus.CREATED,
)
async def register_person(
    corporate_id: str, body: RegisterPersonRequest, use_cases: IdentityUseCasesDep
) -> RegisteredIdResponse:
    """自法人の本人を登録する。"""
    person = await use_cases.register_person.execute(
        corporate_id, PersonNamesInput(**body.model_dump())
    )
    return RegisteredIdResponse(id=str(person.id.value))


@router.post(
    "/corporates/{corporate_id}/staffs/{staff_id}/person-link",
)
async def link_staff_person(
    corporate_id: str,
    staff_id: str,
    body: LinkPersonRequest,
    use_cases: IdentityUseCasesDep,
) -> RegisteredIdResponse:
    """スタッフと本人を変更不能な対応として登録する。"""
    link = await use_cases.link_staff.execute(corporate_id, body.person_id, staff_id)
    return RegisteredIdResponse(id=str(link.id.value))


@router.post("/accounts/{account_id}/reactivation")
async def reactivate_account(
    account_id: str, use_cases: IdentityUseCasesDep
) -> RegisteredIdResponse:
    """個人アカウント全体をベンダーが再開する。"""
    account = await use_cases.reactivate_account.execute(account_id)
    return RegisteredIdResponse(id=str(account.id.value))
