"""Applicationのverify_statutory_record_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.verify_statutory_record import (
    StatutoryRecordSufficiencyDto,
)
from app.application.medication_history.queries.models import VerifyStatutoryRecordQuery


class VerifyStatutoryRecordQueryReader(Protocol):
    async def read(
        self, query: VerifyStatutoryRecordQuery
    ) -> StatutoryRecordSufficiencyDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
