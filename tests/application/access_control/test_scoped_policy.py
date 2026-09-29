"""本人特定済みの操作主体に対する店舗認可。"""

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import (
    AccountPersonId,
    CorporateMembershipId,
    UserAccountId,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

_CORPORATE = CorporateId.generate()
_STORE = StoreId.generate()


def _actor(
    role: ActorRole, *, stores: frozenset[StoreId] | None = None
) -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="検証済み主体",
        roles=frozenset({role}),
        corporate_id=_CORPORATE,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        membership_id=CorporateMembershipId.generate(),
        staff_id=StaffId.generate(),
        store_ids=frozenset({_STORE}) if stores is None else stores,
    )


@pytest.mark.parametrize("role", list(ActorRole))
@pytest.mark.parametrize(
    "permission",
    [
        Permission.VIEW_STORE,
        Permission.VIEW_RECEPTION,
        Permission.VIEW_PRESCRIPTION,
        Permission.VIEW_DISPENSING,
        Permission.VIEW_MEDICATION_HISTORY,
    ],
)
def test_許可店舗の業務記録は各ロールが閲覧できる(
    role: ActorRole, permission: Permission
) -> None:
    AuthorizationService(_actor(role)).require_store(
        permission=permission, target_corporate_id=_CORPORATE, target_store_id=_STORE
    )


@pytest.mark.parametrize(
    "permission",
    [
        Permission.MANAGE_RECEPTION,
        Permission.MANAGE_PRESCRIPTION,
        Permission.MANAGE_DISPENSING,
        Permission.MANAGE_MEDICATION_HISTORY,
    ],
)
def test_店舗業務担当は許可店舗の業務を操作できる(permission: Permission) -> None:
    AuthorizationService(_actor(ActorRole.STORE_OPERATOR)).require_store(
        permission=permission, target_corporate_id=_CORPORATE, target_store_id=_STORE
    )


@pytest.mark.parametrize(
    "permission",
    [
        Permission.MANAGE_STORE,
        Permission.MANAGE_STAFF,
        Permission.MANAGE_RECEPTION,
        Permission.MANAGE_PRESCRIPTION,
        Permission.MANAGE_DISPENSING,
        Permission.MANAGE_MEDICATION_HISTORY,
    ],
)
def test_店舗閲覧者は許可店舗でも更新できない(permission: Permission) -> None:
    with pytest.raises(AuthorizationError):
        AuthorizationService(_actor(ActorRole.STORE_VIEWER)).require_store(
            permission=permission,
            target_corporate_id=_CORPORATE,
            target_store_id=_STORE,
        )


@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
def test_許可外店舗の存在を隠蔽する(role: ActorRole) -> None:
    with pytest.raises(TenantBoundaryNotFoundError):
        AuthorizationService(_actor(role)).require_store(
            permission=Permission.VIEW_DISPENSING,
            target_corporate_id=_CORPORATE,
            target_store_id=StoreId.generate(),
        )


@pytest.mark.parametrize(
    ("permission", "allowed"),
    [
        (Permission.VIEW_PATIENT_HEADING, True),
        (Permission.MANAGE_PATIENT_HEADING, True),
        (Permission.MANAGE_PATIENT, False),
    ],
    ids=["頭書き参照", "頭書き更新", "基本台帳編集"],
)
def test_tc43_21_22_店舗オペレータの頭書き権限を基本台帳権限から分離する(
    permission: Permission, allowed: bool
) -> None:
    authorization = AuthorizationService(_actor(ActorRole.STORE_OPERATOR))

    if allowed:
        authorization.require(permission=permission, target_corporate_id=_CORPORATE)
    else:
        with pytest.raises(AuthorizationError):
            authorization.require(permission=permission, target_corporate_id=_CORPORATE)


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (ActorRole.STORE_OPERATOR, Permission.VIEW_PATIENT_HEADING, True),
        (ActorRole.STORE_OPERATOR, Permission.MANAGE_PATIENT_HEADING, True),
        (ActorRole.STORE_VIEWER, Permission.VIEW_PATIENT_HEADING, True),
        (ActorRole.STORE_VIEWER, Permission.MANAGE_PATIENT_HEADING, False),
        (ActorRole.CORPORATE_ADMIN, Permission.VIEW_PATIENT_HEADING, True),
        (ActorRole.CORPORATE_ADMIN, Permission.MANAGE_PATIENT_HEADING, True),
        (ActorRole.VENDOR_SYSTEM_ADMIN, Permission.VIEW_PATIENT_HEADING, True),
        (ActorRole.VENDOR_SYSTEM_ADMIN, Permission.MANAGE_PATIENT_HEADING, True),
    ],
    ids=[
        "operator参照",
        "operator更新",
        "viewer参照",
        "viewer更新",
        "admin参照",
        "admin更新",
        "vendor参照",
        "vendor更新",
    ],
)
def test_tc43_21_店舗管理者とビューアの頭書き権限を分ける(
    role: ActorRole, permission: Permission, allowed: bool
) -> None:
    authorization = AuthorizationService(_actor(role))

    if allowed:
        authorization.require(permission=permission, target_corporate_id=_CORPORATE)
    else:
        with pytest.raises(AuthorizationError):
            authorization.require(permission=permission, target_corporate_id=_CORPORATE)


def test_空の店舗集合は全店舗許可にならない() -> None:
    with pytest.raises(TenantBoundaryNotFoundError):
        AuthorizationService(
            _actor(ActorRole.STORE_OPERATOR, stores=frozenset())
        ).require_store(
            permission=Permission.VIEW_STORE,
            target_corporate_id=_CORPORATE,
            target_store_id=_STORE,
        )


@pytest.mark.parametrize(
    "permission",
    [
        Permission.VIEW_PATIENT,
        Permission.MANAGE_PATIENT,
        Permission.VIEW_COVERAGE,
        Permission.MANAGE_COVERAGE,
    ],
)
@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
def test_店舗ロールは法人共通台帳へ直接アクセスできない(
    role: ActorRole, permission: Permission
) -> None:
    with pytest.raises(AuthorizationError):
        AuthorizationService(_actor(role)).require(
            permission=permission, target_corporate_id=_CORPORATE
        )


@pytest.mark.parametrize(
    "role",
    [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER, ActorRole.CORPORATE_ADMIN],
)
def test_他法人の店舗を指定しても操作できない(role: ActorRole) -> None:
    with pytest.raises(TenantBoundaryNotFoundError):
        AuthorizationService(_actor(role)).require_store(
            permission=Permission.VIEW_STORE,
            target_corporate_id=CorporateId.generate(),
            target_store_id=_STORE,
        )


def test_法人管理者は自法人の全店舗を参照できる() -> None:
    AuthorizationService(
        _actor(ActorRole.CORPORATE_ADMIN, stores=frozenset())
    ).require_store(
        permission=Permission.VIEW_STORE,
        target_corporate_id=_CORPORATE,
        target_store_id=StoreId.generate(),
    )
