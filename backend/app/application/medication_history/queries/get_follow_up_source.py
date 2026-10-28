"""Applicationのget_follow_up_sourceを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.interfaces.get_follow_up_source_query_reader import (
    GetFollowUpSourceQueryReader,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    FollowUpSourceDto,
)
from app.application.medication_history.queries.models import GetFollowUpSourceQuery
from app.domain.corporate.identifiers import CorporateId


class GetFollowUpSourceUseCase:
    def __init__(
        self,
        reader: GetFollowUpSourceQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(self, query: GetFollowUpSourceQuery) -> FollowUpSourceDto:
        """確定済み元薬歴のEvent参照を返し、他店舗本文は取得しない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        return await self._reader.read(query)
