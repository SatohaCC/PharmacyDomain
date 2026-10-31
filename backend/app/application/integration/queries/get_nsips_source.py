"""Applicationのget_nsips_sourceを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.integration.interfaces.get_nsips_source_query_reader import (
    GetNsipsSourceQueryReader,
)
from app.application.integration.queries.dtos.get_nsips_source import NsipsSourceDto
from app.application.integration.queries.models import GetNsipsSourceQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class GetNsipsSourceUseCase:
    """NSIPS原本データを認可・店舗境界を適用して照会する。"""

    def __init__(
        self,
        reader: GetNsipsSourceQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetNsipsSourceQuery) -> NsipsSourceDto:
        """認可と選択店舗を検証し、原本DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_RECEPTION
        )
        AuthorizationService(self._corporate_access.actor).require_store(
            permission=Permission.VIEW_RECEPTION,
            target_corporate_id=corporate_id,
            target_store_id=store_id,
        )
        return await self._reader.read(query)
