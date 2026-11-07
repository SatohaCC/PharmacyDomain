"""受付の今回記載欄入力値のQueryReader契約。"""

from __future__ import annotations

from typing import Protocol

from app.application.reception.queries.dtos.current_record_values import (
    CurrentRecordFieldValueDto,
)
from app.application.reception.queries.models import GetCurrentRecordValuesQuery


class GetCurrentRecordValuesQueryReader(Protocol):
    """認可済みの受付今回記載欄入力値を返す契約。"""

    async def read(
        self, query: GetCurrentRecordValuesQuery
    ) -> tuple[CurrentRecordFieldValueDto, ...]: ...


__all__ = ["GetCurrentRecordValuesQueryReader"]
