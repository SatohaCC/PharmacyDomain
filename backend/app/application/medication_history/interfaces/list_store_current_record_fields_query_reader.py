"""店舗の今回記載欄設定一覧のQueryReader契約。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.category_catalog import (
    CurrentRecordFieldDto,
)
from app.application.medication_history.queries.models import (
    ListStoreCurrentRecordFieldsQuery,
)


class ListStoreCurrentRecordFieldsQueryReader(Protocol):
    """認可済みの店舗今回記載欄設定一覧を返す契約。"""

    async def read(
        self, query: ListStoreCurrentRecordFieldsQuery
    ) -> tuple[CurrentRecordFieldDto, ...]: ...


__all__ = ["ListStoreCurrentRecordFieldsQueryReader"]
