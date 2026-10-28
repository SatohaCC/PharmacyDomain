"""Applicationのget_prescription_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.prescription.queries.dtos.get_prescription import PrescriptionDto
from app.application.prescription.queries.models import GetPrescriptionQuery


class GetPrescriptionQueryReader(Protocol):
    async def read(self, query: GetPrescriptionQuery) -> PrescriptionDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
