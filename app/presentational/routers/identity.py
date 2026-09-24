"""個人のアカウントと法人アクセス権のHTTP窓口。"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.access_control.models import ResolvedActorContext
from app.application.common.pagination import Page
from app.application.identity.dto import (
    CurrentActorDto,
    InvitationViewDto,
    MembershipViewDto,
)
from app.application.identity.invite_user import InviteUserCommand, IssuedInvitation
from app.application.identity.resolve_actor import VerifiedSubject
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.shared.person_name import PersonNames
from app.infrastructure.di.root import PostgresCompositionRoot
from app.presentational.dependencies import (
    Actor,
    IdentityUseCasesDep,
    VerifiedSubjectDep,
    get_actor_context,
    get_composition_root,
    get_verified_subject,
)
from app.presentational.errors import error_responses
from app.presentational.exceptions import AuthenticationError
from app.presentational.schemas import RegisteredIdResponse, RequestModel

#: 通常のIdentity操作。認証はルータ単位で掛ける。
#:
#: ルート関数の引数に頼ると、新しいルートを足したときに書き忘れた1本だけが
#: 無認証で公開される。アカウントと法人アクセス権を扱うルータで、それは最も
#: 起きてはいけない漏れ方をする。
router = APIRouter(
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

#: 招待の受諾だけは、内部アカウントがまだ無い本人も通す。
#:
#: 認証の種類が違うので同じルータには置けない。ルート単位で ``Depends`` を
#: 書き分けると、本来Actorを要求すべきルートを間違えてこちらの認証で公開して
#: しまう余地が残るため、ルータごと分ける。
acceptance_router = APIRouter(
    tags=["identity"],
    dependencies=[Depends(get_verified_subject)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class InviteUserRequest(RequestModel):
    """本人IDを必須とする招待。本人確認結果やベンダー権限は受けない。"""

    person_id: str
    addressee: str
    role: MembershipRole
    expires_at: datetime
    store_ids: tuple[str, ...] = ()
    staff_id: str | None = None


class AcceptInvitationRequest(RequestModel):
    """受諾の秘密だけを受け、本人は認証境界で決める。"""

    secret: str


class ChangeMembershipRequest(RequestModel):
    """同じ本人・アカウントの法人アクセス権の変更。"""

    status: AccountStatus | None = None
    role: MembershipRole | None = None
    store_ids: tuple[str, ...] | None = None


@router.post(
    "/corporates/{corporate_id}/user-invitations",
    response_model=IssuedInvitation,
    status_code=HTTPStatus.CREATED,
)
async def invite_user(
    corporate_id: str, body: InviteUserRequest, use_cases: IdentityUseCasesDep
) -> IssuedInvitation:
    """本人指定の招待を発行し、秘密を一度だけ返す。"""
    return await use_cases.invite.execute(
        InviteUserCommand(corporate_id=corporate_id, **body.model_dump())
    )


@acceptance_router.post(
    "/user-invitations/acceptance",
    response_model=RegisteredIdResponse,
)
async def accept_invitation(
    body: AcceptInvitationRequest,
    subject: VerifiedSubjectDep,
    root: Annotated[PostgresCompositionRoot, Depends(get_composition_root)],
) -> RegisteredIdResponse:
    """内部アカウント未作成でも検証済みの外部主体で招待を受諾できる。"""
    account = await root.accept_invitation(subject, body.secret)
    return RegisteredIdResponse(id=str(account.id.value))


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
    )
    return RegisteredIdResponse(id=str(membership.id.value))


@router.post(
    "/accounts/{account_id}/suspension",
    response_model=RegisteredIdResponse,
)
async def suspend_account(
    account_id: str, use_cases: IdentityUseCasesDep
) -> RegisteredIdResponse:
    """本人に対応する個人アカウント全体をベンダーが停止する。"""
    account = await use_cases.suspend_account.execute(account_id)
    return RegisteredIdResponse(id=str(account.id.value))


@router.get("/me")
async def get_me(actor: Actor, use_cases: IdentityUseCasesDep) -> CurrentActorDto:
    """現在有効な本人・アカウント・法人アクセス範囲を返す。"""
    if not isinstance(actor, ResolvedActorContext):
        raise AuthenticationError("本人を特定できません。")
    current = await use_cases.resolve_actor.execute(
        VerifiedSubject(principal_id=actor.principal_id)
    )
    return CurrentActorDto.from_actor(current)


# 停止・再開の理由は受け取らない。必須で受けて捨てていた時期があったが、
# 保存先が無いので「必須項目を埋めたのにどこにも残らない」応答になっていた。
# 理由を残すなら、StoreStatusChange と同じ形の履歴を CorporateMembership へ
# 持たせる必要がある（操作者と記録時刻も要る）。本文を取らない操作として扱う。


class RegisterPersonRequest(RequestModel):
    """招待の対象となる本人を登録する。"""

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


@router.post(
    "/corporates/{corporate_id}/user-invitations/{invitation_id}/cancellation",
)
async def cancel_invitation(
    corporate_id: str, invitation_id: str, use_cases: IdentityUseCasesDep
) -> None:
    """未受諾の招待を取り消す。"""
    await use_cases.cancel_invitation.execute(corporate_id, invitation_id)


@router.get(
    "/corporates/{corporate_id}/user-invitations/{invitation_id}",
)
async def get_invitation(
    corporate_id: str, invitation_id: str, use_cases: IdentityUseCasesDep
) -> InvitationViewDto:
    """招待の秘密を再取得させず状態を返す。"""
    return await use_cases.get_invitation.execute(corporate_id, invitation_id)


@router.post(
    "/corporates/{corporate_id}/people",
    status_code=HTTPStatus.CREATED,
)
async def register_person(
    corporate_id: str, body: RegisterPersonRequest, use_cases: IdentityUseCasesDep
) -> RegisteredIdResponse:
    """自法人への招待に必要な本人を登録する。"""
    person = await use_cases.register_person.execute(
        corporate_id, PersonNames.create(**body.model_dump())
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
