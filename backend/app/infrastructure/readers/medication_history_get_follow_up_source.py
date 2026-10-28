"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.common.exceptions import NotFoundError
from app.application.medication_history.interfaces.get_follow_up_source_query_reader import (
    GetFollowUpSourceQueryReader,
)
from app.application.medication_history.queries.dtos.get_medication_history import (
    FollowUpSourceDto,
)
from app.application.medication_history.queries.models import GetFollowUpSourceQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import MedicationHistoryRepository


class GetFollowUpSourceProjection(GetFollowUpSourceQueryReader):
    """確定済み薬歴から本文を読まず関連Eventだけを取り出す。"""

    def __init__(self, repository: MedicationHistoryRepository) -> None:
        self._repository = repository

    async def read(self, query: GetFollowUpSourceQuery) -> FollowUpSourceDto:
        """確定済み元薬歴のEvent参照を返し、他店舗本文は取得しない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        source = await self._repository.get_finalized_source_for_follow_up(
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        if source is None:
            raise NotFoundError(
                "指定された確定済み薬歴が見つかりません。",
                code="MEDICATION_HISTORY_NOT_FOUND",
            )
        return FollowUpSourceDto(event_id=source.event_id, patient_id=source.patient_id)
