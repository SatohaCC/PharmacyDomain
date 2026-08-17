"""認証・認可境界で扱う値。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.corporate.primitives import CorporateId


class ActorRole(StrEnum):
    """アプリケーションが認識する最小限の操作主体ロール。"""

    VENDOR_SYSTEM_ADMIN = "vendor_system_admin"
    CORPORATE_ADMIN = "corporate_admin"


class Permission(StrEnum):
    """ユースケースが要求する操作権限。"""

    REGISTER_CORPORATE = "register_corporate"
    VIEW_CORPORATE = "view_corporate"
    MANAGE_CORPORATE = "manage_corporate"
    MANAGE_CORPORATE_STATUS = "manage_corporate_status"
    VIEW_STORE = "view_store"
    MANAGE_STORE = "manage_store"
    VIEW_STAFF = "view_staff"
    MANAGE_STAFF = "manage_staff"
    VIEW_PATIENT = "view_patient"
    MANAGE_PATIENT = "manage_patient"
    VIEW_COVERAGE = "view_coverage"
    MANAGE_COVERAGE = "manage_coverage"


@dataclass(frozen=True, kw_only=True)
class ActorContext:
    """認証・セッション層から渡される、改ざんされていない操作主体。"""

    principal_id: str
    roles: frozenset[ActorRole]
    #: 法人管理者の所属法人。ベンダー管理者のグローバル権限では ``None`` を許容する。
    corporate_id: CorporateId | None = None

    def __post_init__(self) -> None:
        """ロールと法人スコープの組み合わせを早期に検証する。"""
        if ActorRole.CORPORATE_ADMIN in self.roles and self.corporate_id is None:
            raise ValueError("法人管理者には所属法人が必要です。")

    @classmethod
    def vendor_system_admin(
        cls,
        *,
        principal_id: str,
    ) -> ActorContext:
        """全法人を操作できるベンダーシステム管理者を生成する。"""
        return cls(
            principal_id=principal_id,
            roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        )

    @classmethod
    def corporate_admin(
        cls,
        *,
        principal_id: str,
        corporate_id: CorporateId,
    ) -> ActorContext:
        """指定法人だけを操作できる法人管理者を生成する。"""
        return cls(
            principal_id=principal_id,
            roles=frozenset({ActorRole.CORPORATE_ADMIN}),
            corporate_id=corporate_id,
        )
