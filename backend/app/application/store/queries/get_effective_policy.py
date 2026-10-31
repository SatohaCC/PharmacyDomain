"""Applicationのget_effective_policyを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.store.errors import StoreNotFoundError
from app.application.store.interfaces.get_effective_policy_query_reader import (
    GetEffectivePolicyQueryReader,
)
from app.application.store.queries.dtos.get_effective_policy import EffectivePolicyDto
from app.application.store.queries.models import GetEffectivePolicyQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class GetEffectivePolicyUseCase:
    """店舗の実効ポリシーを取得する。"""

    def __init__(
        self,
        reader: GetEffectivePolicyQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetEffectivePolicyQuery) -> EffectivePolicyDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        store_id = StoreId.parse(query.store_id)
        try:
            AuthorizationService(self._corporate_access.actor).require_store(
                permission=Permission.VIEW_STORE,
                target_corporate_id=corporate_id,
                target_store_id=store_id,
            )
        except TenantBoundaryNotFoundError as error:
            raise StoreNotFoundError() from error
        return await self._reader.read(query)
