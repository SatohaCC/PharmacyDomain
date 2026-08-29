"""操作主体と対象法人の認可ポリシー。"""

from __future__ import annotations

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorContext, ActorRole, Permission
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.primitives import CorporateId

_CORPORATE_ADMIN_PERMISSIONS = frozenset(
    {
        Permission.VIEW_CORPORATE,
        Permission.MANAGE_CORPORATE,
        Permission.VIEW_STORE,
        Permission.MANAGE_STORE,
        Permission.VIEW_STAFF,
        Permission.MANAGE_STAFF,
        Permission.VIEW_PATIENT,
        Permission.MANAGE_PATIENT,
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
    }
)

_VENDOR_ONLY_PERMISSIONS = frozenset(
    {
        Permission.REGISTER_CORPORATE,
        Permission.MANAGE_CORPORATE_STATUS,
        # 薬価基準は国が定める参照データであり、法人ごとに内容が違わない。
        # 取り込みは全法人に影響するのでベンダーシステム管理者専用にする。
        Permission.MANAGE_MEDICINE_CATALOG,
    }
)


def _verify_permission_classification(
    *,
    vendor_only: frozenset[Permission],
    corporate_admin: frozenset[Permission],
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


_verify_permission_classification(
    vendor_only=_VENDOR_ONLY_PERMISSIONS,
    corporate_admin=_CORPORATE_ADMIN_PERMISSIONS,
)


class AuthorizationService:
    """認証済みActorに対するアプリケーション権限を判定する。"""

    def __init__(self, actor: ActorContext) -> None:
        self._actor = actor

    @property
    def actor(self) -> ActorContext:
        """現在の操作主体を返す。"""
        return self._actor

    def _deny(self, permission: Permission) -> None:
        raise AuthorizationError(
            f"操作主体 '{self._actor.principal_id}' には"
            f"権限 '{permission.value}' がありません。"
        )

    def require(
        self,
        *,
        permission: Permission,
        target_corporate_id: CorporateId,
    ) -> None:
        """指定された権限と法人スコープを満たすことを要求する。"""
        # ベンダーシステム管理者は全法人の全操作を許可
        if ActorRole.VENDOR_SYSTEM_ADMIN in self._actor.roles:
            return

        # 法人管理者が他法人のリソースにアクセスした場合は存在を隠蔽（404）
        if (
            self._actor.corporate_id is not None
            and self._actor.corporate_id != target_corporate_id
        ):
            raise TenantBoundaryNotFoundError()

        # 自法人の操作で、かつ法人管理者に許可された権限であること
        # (注: 直前の境界チェックで corporate_id != target_corporate_id の場合は例外送出済みのため、
        #  self._actor.corporate_id == target_corporate_id は常に真ですが、防衛的プログラミングとして二重確認)
        if (
            ActorRole.CORPORATE_ADMIN in self._actor.roles
            and permission in _CORPORATE_ADMIN_PERMISSIONS
            and self._actor.corporate_id == target_corporate_id
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
