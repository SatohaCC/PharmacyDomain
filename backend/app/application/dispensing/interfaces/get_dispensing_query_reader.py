"""Applicationのget_dispensing_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.dispensing.queries.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.queries.models import GetDispensingQuery


class GetDispensingQueryReader(Protocol):
    async def read(self, query: GetDispensingQuery) -> DispensingProcessDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
