"""Applicationのget_patient_medical_profile_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.get_patient_medical_profile import (
    PatientMedicalProfileDto,
)
from app.application.medication_history.queries.models import (
    GetPatientMedicalProfileQuery,
)


class GetPatientMedicalProfileQueryReader(Protocol):
    async def read(
        self, query: GetPatientMedicalProfileQuery
    ) -> PatientMedicalProfileDto:
        """認可済みの検索条件から、不変な参照結果だけを返す。"""
        ...
