"""Applicationのrevoke_store_closureを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import (
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.store.commands.dtos.get_store import StoreDto
from app.application.store.commands.services.support import load_store_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import StoreStatusReason
from app.domain.store.repositories import StoreRepository


@dataclass(frozen=True, kw_only=True)
class RevokeStoreClosureCommand:
    """閉局の取消。理由は必須で、記録者と記録時刻は入力として受けない。"""

    corporate_id: str
    store_id: str
    reason: str


class RevokeStoreClosureUseCase:
    """ベンダーシステム管理者だけが、誤って登録された閉局を取り消す。

    権限判定をルータへ持ち込まない。ここで要求すれば、経路が増えても判定は
    1箇所のままである。
    """

    def __init__(
        self,
        stores: StoreRepository,
        access: CorporateAccessBoundary,
        clock: Clock,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._stores = stores
        self._access = access
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, command: RevokeStoreClosureCommand) -> StoreDto:
        """閉局を取り消して休止へ戻す。任命は復元しない。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")
        AuthorizationService(self._access.actor).require_vendor_system_admin(
            permission=Permission.REVOKE_STORE_CLOSURE
        )
        store = await load_store_or_raise(
            self._stores,
            corporate_id=corporate_id,
            store_id=StoreId.parse(command.store_id),
        )
        actor = self._access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError("閉局の取消には本人とアカウントの特定が必要です。")
        updated = store.revoke_closure(
            reason=StoreStatusReason(command.reason),
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=self._clock.now(),
        )
        await self._stores.save(updated)
        return StoreDto.from_entity(updated)
