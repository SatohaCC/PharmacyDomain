"""Applicationのget_patient_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.queries.dtos.get_patient import PatientDto
from app.application.patient.queries.models import GetPatientQuery


class GetPatientQueryReader(Protocol):
    async def read(self, query: GetPatientQuery) -> PatientDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
