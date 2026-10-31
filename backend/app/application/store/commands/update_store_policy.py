"""Applicationのupdate_store_policyを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.services.support import load_store_or_raise
from app.application.store.interfaces.management import CorporatePolicyBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.exceptions import StorePolicyOverrideConflictError
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository
from app.domain.store.value_objects import StorePolicy


@dataclass(frozen=True, kw_only=True)
class UpdateStorePolicyCommand:
    """店舗ポリシー更新の入力データ。"""

    corporate_id: str
    store_id: str
    require_prescription_audit: bool | None = None
    prohibit_self_verification: bool | None = None


class UpdateStorePolicyUseCase:
    """店舗ポリシーを更新する。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
        corporate_policy: CorporatePolicyBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._corporate_policy = corporate_policy

    async def execute(self, command: UpdateStorePolicyCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        overridable = await self._corporate_policy.get_overridable(corporate_id)

        if (
            command.require_prescription_audit is not None
            and not overridable.require_prescription_audit_overridable
        ):
            raise StorePolicyOverrideConflictError(
                "法人で処方鑑査必須ポリシーの上書きが禁止されています。"
            )
        if (
            command.prohibit_self_verification is not None
            and not overridable.prohibit_self_verification_overridable
        ):
            raise StorePolicyOverrideConflictError(
                "法人で自己鑑査禁止ポリシーの上書きが禁止されています。"
            )

        new_policy = StorePolicy(
            require_prescription_audit=command.require_prescription_audit,
            prohibit_self_verification=command.prohibit_self_verification,
        )
        store = store.change_policy(new_policy)
        await self._repository.save(store)
