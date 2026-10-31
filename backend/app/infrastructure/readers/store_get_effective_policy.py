"""Repositoryから実効ポリシーDTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from typing import Literal

from app.application.store.errors import StoreNotFoundError
from app.application.store.interfaces.get_effective_policy_query_reader import (
    GetEffectivePolicyQueryReader,
)
from app.application.store.queries.dtos.get_effective_policy import (
    EffectivePolicyDto,
    EffectivePolicyItemDto,
)
from app.application.store.queries.models import GetEffectivePolicyQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.repositories import CorporateRepository
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository
from app.infrastructure.readers.helpers.store_support import load_store_or_raise


class GetEffectivePolicyProjection(GetEffectivePolicyQueryReader):
    """店舗の実効ポリシー投影リーダー。"""

    def __init__(
        self,
        corporate_repository: CorporateRepository,
        store_repository: StoreRepository,
    ) -> None:
        self._corporate_repository = corporate_repository
        self._store_repository = store_repository

    async def read(self, query: GetEffectivePolicyQuery) -> EffectivePolicyDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        corporate = await self._corporate_repository.get(corporate_id)
        if corporate is None:
            raise StoreNotFoundError("指定された店舗が見つかりません。")
        store = await load_store_or_raise(
            self._store_repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )

        corp_audit = corporate.policy.require_prescription_audit
        store_audit = store.policy.require_prescription_audit
        if corp_audit.overridable and store_audit is not None:
            audit_source: Literal["corporate", "store"] = "store"
            audit_value = store_audit
        else:
            audit_source = "corporate"
            audit_value = corp_audit.value

        corp_self = corporate.policy.prohibit_self_verification
        store_self = store.policy.prohibit_self_verification
        if corp_self.overridable and store_self is not None:
            self_source: Literal["corporate", "store"] = "store"
            self_value = store_self
        else:
            self_source = "corporate"
            self_value = corp_self.value

        return EffectivePolicyDto(
            require_prescription_audit=EffectivePolicyItemDto(
                value=audit_value, source=audit_source
            ),
            prohibit_self_verification=EffectivePolicyItemDto(
                value=self_value, source=self_source
            ),
        )
