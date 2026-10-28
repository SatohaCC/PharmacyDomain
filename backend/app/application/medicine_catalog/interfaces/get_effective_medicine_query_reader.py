"""Applicationのget_effective_medicine_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medicine_catalog.queries.dtos.get_medicine import MedicineDto
from app.application.medicine_catalog.queries.models import GetEffectiveMedicineQuery


class GetEffectiveMedicineQueryReader(Protocol):
    async def read(self, query: GetEffectiveMedicineQuery) -> MedicineDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
