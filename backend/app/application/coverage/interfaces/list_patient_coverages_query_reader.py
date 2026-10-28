"""Applicationのlist_patient_coverages_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto,
)
from app.application.coverage.queries.models import ListPatientCoveragesQuery


class ListPatientCoveragesQueryReader(Protocol):
    async def read(self, query: ListPatientCoveragesQuery) -> list[PatientCoverageDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
