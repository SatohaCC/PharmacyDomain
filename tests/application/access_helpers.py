"""アプリケーション層テストで使う認可コンテキスト。"""

from __future__ import annotations

from app.application.access_control import ActorContext, AuthorizationService
from app.application.corporate import CorporateAccessService
from app.domain.corporate import (
    Corporate,
    CorporateId,
    CorporateName,
    CorporateRepresentativeName,
    CorporateStatus,
)
from app.domain.corporate.repository import CorporateRepository


class AutoProvisioningCorporateRepository(CorporateRepository):
    """既存の店舗・スタッフテスト用に対象法人を自動提供するフェイク。"""

    def __init__(self) -> None:
        self._inactive_corporate_ids: set[CorporateId] = set()

    def set_inactive(self, corporate_id: CorporateId) -> None:
        """指定された法人を無効状態として認識させる。"""
        self._inactive_corporate_ids.add(corporate_id)

    async def get(self, corporate_id: CorporateId) -> Corporate:
        status = (
            CorporateStatus.INACTIVE
            if corporate_id in self._inactive_corporate_ids
            else CorporateStatus.ACTIVE
        )
        return Corporate(
            id=corporate_id,
            name=CorporateName(f"テスト法人-{corporate_id.value}"),
            representative_name=CorporateRepresentativeName.create(
                last_name="山田",
                first_name="太郎",
            ),
            status=status,
        )

    async def save(self, corporate: Corporate) -> None:
        if not corporate.is_active:
            self._inactive_corporate_ids.add(corporate.id)
        else:
            self._inactive_corporate_ids.discard(corporate.id)

    async def exists_by_name(
        self,
        name: CorporateName,
        *,
        excluding_id: CorporateId | None = None,
    ) -> bool:
        del name, excluding_id
        return False


def create_vendor_corporate_access() -> CorporateAccessService:
    """既存ユースケーステストを実行するベンダー管理者のアクセス境界。"""
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(),
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="test-vendor-admin")
        ),
    )


def create_vendor_corporate_access_for(
    repository: CorporateRepository,
) -> CorporateAccessService:
    """実在法人を扱うテスト用のベンダー管理者境界。"""
    return CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="test-vendor-admin")
        ),
    )


def create_vendor_authorization() -> AuthorizationService:
    """法人登録など、対象法人をまだ持たない操作の認可コンテキスト。"""
    return AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="test-vendor-admin")
    )
