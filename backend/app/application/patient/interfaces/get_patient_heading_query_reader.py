"""Applicationのget_patient_heading_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.queries.dtos.get_patient_heading import PatientHeadingDto
from app.application.patient.queries.models import GetPatientHeadingQuery


class GetPatientHeadingQueryReader(Protocol):
    async def read(self, query: GetPatientHeadingQuery) -> PatientHeadingDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
