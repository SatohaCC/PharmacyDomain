"""Applicationのeffective_policy_resolverを定義する。"""

from __future__ import annotations

from app.application.dispensing.interfaces.references import (
    DispensingPolicyBoundary,
    DispensingPolicySnapshot,
)
from app.application.store.interfaces.management import (
    CorporatePolicyBoundary,
    CorporatePolicyOverridableSnapshot,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.repositories import CorporateRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


class EffectivePolicyResolver(CorporatePolicyBoundary, DispensingPolicyBoundary):
    """法人ポリシーと店舗ポリシーから実効ポリシーを解決するアダプタ。"""

    def __init__(
        self,
        corporate_repository: CorporateRepository,
        store_repository: StoreRepository,
    ) -> None:
        self._corporate_repository = corporate_repository
        self._store_repository = store_repository

    async def get_overridable(
        self, corporate_id: CorporateId
    ) -> CorporatePolicyOverridableSnapshot:
        corporate = await self._corporate_repository.get(corporate_id)
        if corporate is None:
            return CorporatePolicyOverridableSnapshot(
                require_prescription_audit_overridable=False,
                prohibit_self_verification_overridable=False,
            )
        return CorporatePolicyOverridableSnapshot(
            require_prescription_audit_overridable=corporate.policy.require_prescription_audit.overridable,
            prohibit_self_verification_overridable=corporate.policy.prohibit_self_verification.overridable,
        )

    async def get_effective_policy(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> DispensingPolicySnapshot:
        corporate = await self._corporate_repository.get(corporate_id)
        if corporate is None:
            return DispensingPolicySnapshot()
        store = await self._store_repository.get(store_id)
        if store is None or store.corporate_id != corporate_id:
            return DispensingPolicySnapshot()

        corp_audit = corporate.policy.require_prescription_audit
        store_audit = store.policy.require_prescription_audit
        if corp_audit.overridable and store_audit is not None:
            effective_audit = store_audit
        else:
            effective_audit = corp_audit.value

        corp_self = corporate.policy.prohibit_self_verification
        store_self = store.policy.prohibit_self_verification
        if corp_self.overridable and store_self is not None:
            effective_self = store_self
        else:
            effective_self = corp_self.value

        return DispensingPolicySnapshot(
            require_prescription_audit=effective_audit,
            prohibit_self_verification=effective_self,
        )
