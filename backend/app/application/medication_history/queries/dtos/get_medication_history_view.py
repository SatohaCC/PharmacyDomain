"""Applicationのget_medication_history_viewを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.medication_history.queries.dtos.get_medication_history import (
    MedicationHistoryDto,
)


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryPatientProfileDto:
    """薬歴表示時に参照する患者の現行プロフィール。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str | None
    gender: str | None
    postal_code: str | None
    address: str | None
    phone_number: str | None


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryViewDto:
    """確定薬歴と読取時点の患者プロフィール。"""

    record: MedicationHistoryDto
    current_patient_profile: MedicationHistoryPatientProfileDto
