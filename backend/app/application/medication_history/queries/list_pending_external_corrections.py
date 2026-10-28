"""Applicationのlist_pending_external_correctionsを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import ActorRole, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.common.pagination import MAX_PAGE_SIZE, Page
from app.application.medication_history.interfaces.list_pending_external_corrections_query_reader import (
    ListPendingExternalCorrectionsQueryReader,
)
from app.application.medication_history.queries.dtos.list_pending_external_corrections import (
    PendingExternalCorrectionDto,
)
from app.application.medication_history.queries.models import (
    ListPendingExternalCorrectionsQuery,
)
from app.application.medication_history.queries.services.list_pending_external_corrections import (
    _decode_cursor,
)
from app.application.medication_history.values import parse_enum
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.primitives import ExternalCorrectionStatus
from app.domain.store.identifiers import StoreId


class ListPendingExternalCorrectionsUseCase:
    def __init__(
        self,
        reader: ListPendingExternalCorrectionsQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListPendingExternalCorrectionsQuery
    ) -> Page[PendingExternalCorrectionDto]:
        """状態、法人、店舗をRepository検索へ渡し、安定cursorで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        if query.limit < 1 or query.limit > MAX_PAGE_SIZE:
            raise ValueError(
                f"一覧件数は1から{MAX_PAGE_SIZE}の範囲で指定してください。"
            )
        access = AuthorizationService(self._corporate_access.actor)
        actor = access.actor
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        store_id = StoreId.parse(query.store_id) if query.store_id is not None else None
        if store_id is not None:
            access.require_store(
                permission=Permission.VIEW_MEDICATION_HISTORY,
                target_corporate_id=corporate_id,
                target_store_id=store_id,
            )
        elif not actor.roles & {
            ActorRole.VENDOR_SYSTEM_ADMIN,
            ActorRole.CORPORATE_ADMIN,
        }:
            raise AuthorizationError("店舗ロールでは店舗IDを指定してください。")
        parse_enum(
            ExternalCorrectionStatus, query.status, "訂正状態"
        ) if query.status is not None else None
        _decode_cursor(query.cursor) if query.cursor is not None else None
        return await self._reader.read(query)
