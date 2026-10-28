"""Applicationのlist_patient_external_identifiers_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import ListPatientExternalIdentifiersQuery


class ListPatientExternalIdentifiersQueryReader(Protocol):
    async def read(
        self, query: ListPatientExternalIdentifiersQuery
    ) -> list[PatientExternalIdentifierDto]:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
