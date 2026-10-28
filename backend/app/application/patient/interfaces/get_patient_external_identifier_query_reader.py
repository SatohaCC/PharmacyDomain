"""Applicationのget_patient_external_identifier_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import GetPatientExternalIdentifierQuery


class GetPatientExternalIdentifierQueryReader(Protocol):
    async def read(
        self, query: GetPatientExternalIdentifierQuery
    ) -> PatientExternalIdentifierDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
