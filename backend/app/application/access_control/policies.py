"""Applicationのpoliciesを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.errors import (
    StoreContextRequiredError,
    TenantBoundaryNotFoundError,
)
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId

_CORPORATE_ADMIN_PERMISSIONS = frozenset(
    {
        Permission.VIEW_CORPORATE,
        Permission.MANAGE_CORPORATE,
        Permission.VIEW_STORE,
        Permission.MANAGE_STORE,
        Permission.VIEW_STAFF,
        Permission.MANAGE_STAFF,
        Permission.MANAGE_STORE_USERS,
        Permission.VIEW_PATIENT,
        Permission.MANAGE_PATIENT,
        Permission.VIEW_PATIENT_HEADING,
        Permission.MANAGE_PATIENT_HEADING,
        Permission.VIEW_COVERAGE,
        Permission.MANAGE_COVERAGE,
        Permission.VIEW_RECEPTION,
        Permission.MANAGE_RECEPTION,
        Permission.VIEW_PRESCRIPTION,
        Permission.MANAGE_PRESCRIPTION,
        Permission.VIEW_DISPENSING,
        Permission.MANAGE_DISPENSING,
        Permission.VIEW_MEDICATION_HISTORY,
        Permission.MANAGE_MEDICATION_HISTORY,
        Permission.VIEW_EVENT,
        Permission.MANAGE_EVENT,
        Permission.MANAGE_EVENT_DEFINITION,
    }
)
_STORE_VIEW_PERMISSIONS = frozenset(
    {
        Permission.VIEW_STORE,
        Permission.VIEW_STAFF,
        Permission.VIEW_RECEPTION,
        Permission.VIEW_PRESCRIPTION,
        Permission.VIEW_DISPENSING,
        Permission.VIEW_MEDICATION_HISTORY,
        Permission.VIEW_EVENT,
        Permission.VIEW_PATIENT_HEADING,
    }
)
_STORE_WRITE_PERMISSIONS = frozenset(
    {
        Permission.MANAGE_RECEPTION,
        Permission.MANAGE_PRESCRIPTION,
        Permission.MANAGE_DISPENSING,
        Permission.MANAGE_MEDICATION_HISTORY,
        Permission.MANAGE_EVENT,
        Permission.MANAGE_PATIENT_HEADING,
    }
)
_STORE_BUSINESS_PERMISSIONS = (
    _STORE_VIEW_PERMISSIONS - {Permission.VIEW_STORE, Permission.VIEW_STAFF}
) | _STORE_WRITE_PERMISSIONS
_VENDOR_ONLY_PERMISSIONS = frozenset(
    {
        Permission.REGISTER_CORPORATE,
        Permission.MANAGE_CORPORATE_STATUS,
        Permission.MANAGE_MEDICINE_CATALOG,
        Permission.REVOKE_STORE_CLOSURE,
    }
)


def _verify_permission_classification(
    *, vendor_only: frozenset[Permission], corporate_admin: frozenset[Permission]
) -> None:
    """権限分類の網羅性と排他性を検証する。

    分類漏れをモジュール読み込み時に落とすための不変条件チェックです。
    最適化実行（``python -O``）でも省略されないよう、``assert`` ではなく
    ``RuntimeError`` を送出します。
    """
    if set(Permission) != vendor_only | corporate_admin:
        raise RuntimeError(
            "Permission Enum のすべての項目がいずれかの権限集合に分類されていません。"
        )
    if not vendor_only.isdisjoint(corporate_admin):
        raise RuntimeError("ベンダー専用権限と法人管理者権限に重複が存在します。")


def _store_role_allows(actor: ResolvedActorContext, permission: Permission) -> bool:
    """店舗ロールがその操作を行えるか。

    ``require`` と ``require_store`` の両方が同じ判定を必要とする。以前は同一の
    集合リテラルが2箇所に置かれており、片方へ権限を足すと、同じ操作が入口に
    よって通ったり通らなかったりする状態になりえた。
    """
    if permission == Permission.MANAGE_STORE_USERS:
        return ActorRole.STORE_MANAGER in actor.roles
    if permission in _STORE_VIEW_PERMISSIONS:
        return bool(
            actor.roles
            & {
                ActorRole.STORE_OPERATOR,
                ActorRole.STORE_VIEWER,
                ActorRole.STORE_MANAGER,
            }
        )
    if permission in _STORE_WRITE_PERMISSIONS:
        return bool(actor.roles & {ActorRole.STORE_OPERATOR, ActorRole.STORE_MANAGER})
    return False


class AuthorizationService:
    """認証済みActorに対するアプリケーション権限を判定する。"""

    def __init__(self, actor: ActorContext) -> None:
        self._actor = actor

    def require_store(
        self,
        *,
        permission: Permission,
        target_corporate_id: CorporateId,
        target_store_id: StoreId,
    ) -> None:
        """本人の法人権限と対象店舗への操作権限を確認する。"""
        if ActorRole.VENDOR_SYSTEM_ADMIN in self._actor.roles or (
            ActorRole.CORPORATE_ADMIN in self._actor.roles
            and permission not in _STORE_BUSINESS_PERMISSIONS
        ):
            self.require(permission=permission, target_corporate_id=target_corporate_id)
            return
        actor = self._actor
        if (
            not isinstance(actor, ResolvedActorContext)
            or actor.corporate_id != target_corporate_id
        ):
            raise TenantBoundaryNotFoundError()
        if (
            permission in _STORE_BUSINESS_PERMISSIONS
            and actor.require_store_selection
            and actor.selected_store_id is None
        ):
            raise StoreContextRequiredError()
        if (
            permission in _STORE_BUSINESS_PERMISSIONS
            and actor.selected_store_id is not None
            and target_store_id != actor.selected_store_id
        ):
            raise TenantBoundaryNotFoundError()
        if target_store_id not in actor.store_ids:
            raise TenantBoundaryNotFoundError()
        if ActorRole.CORPORATE_ADMIN in actor.roles:
            self.require(permission=permission, target_corporate_id=target_corporate_id)
            return
        if (
            permission == Permission.MANAGE_STORE_USERS
            and target_store_id not in actor.managed_store_ids
        ):
            self._deny(permission)
        if _store_role_allows(actor, permission):
            return
        self._deny(permission)

    @property
    def actor(self) -> ActorContext:
        """現在の操作主体を返す。"""
        return self._actor

    def _deny(self, permission: Permission) -> None:
        raise AuthorizationError(
            f"操作主体 '{self._actor.principal_id}' には権限 '{permission.value}' がありません。"
        )

    def require(
        self, *, permission: Permission, target_corporate_id: CorporateId
    ) -> None:
        """指定された権限と法人スコープを満たすことを要求する。"""
        if ActorRole.VENDOR_SYSTEM_ADMIN in self._actor.roles:
            return
        if (
            self._actor.corporate_id is not None
            and self._actor.corporate_id != target_corporate_id
        ):
            raise TenantBoundaryNotFoundError()
        actor = self._actor
        if (
            isinstance(actor, ResolvedActorContext)
            and permission in _STORE_BUSINESS_PERMISSIONS
            and actor.require_store_selection
            and actor.selected_store_id is None
        ):
            raise StoreContextRequiredError()
        if (
            ActorRole.CORPORATE_ADMIN in self._actor.roles
            and permission in _CORPORATE_ADMIN_PERMISSIONS
            and (self._actor.corporate_id == target_corporate_id)
        ):
            return
        if (
            isinstance(actor, ResolvedActorContext)
            and actor.corporate_id == target_corporate_id
            and _store_role_allows(actor, permission)
        ):
            return
        self._deny(permission)

    def require_vendor_system_admin(self, *, permission: Permission) -> None:
        """ベンダーシステム管理者専用操作を要求する。"""
        if permission not in _VENDOR_ONLY_PERMISSIONS:
            raise ValueError(
                f"権限 '{permission.value}' はベンダーシステム管理者専用権限ではありません。"
            )
        if ActorRole.VENDOR_SYSTEM_ADMIN not in self._actor.roles:
            self._deny(permission)


# 定義を読み込んだ時点で、対応表の不足を最適化実行時にも拒否する。
_verify_permission_classification(
    vendor_only=_VENDOR_ONLY_PERMISSIONS, corporate_admin=_CORPORATE_ADMIN_PERMISSIONS
)
