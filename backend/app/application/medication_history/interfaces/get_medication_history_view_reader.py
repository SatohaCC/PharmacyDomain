"""Applicationのget_medication_history_view_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.medication_history.queries.dtos.get_medication_history_view import (
    MedicationHistoryPatientProfileDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId


class CurrentPatientProfileBoundary(Protocol):
    """Patient集約から読取時点のプロフィールを取得する境界。"""

    async def get_current_profile(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> MedicationHistoryPatientProfileDto | None:
        """法人・患者IDでプロフィールを取得する。"""
        ...
