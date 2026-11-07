"""Applicationのlist_patients用DTOを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.optional_conversion import unwrap
from app.domain.patient.entities import Patient


@dataclass(frozen=True, kw_only=True)
class PatientSummaryDto:
    """患者一覧用サマリDTO。"""

    id: str
    patient_number: int
    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str | None
    gender: str | None = None
    phone_number: str | None = None
    status: str = "active"

    @classmethod
    def from_entity(cls, patient: Patient) -> PatientSummaryDto:
        """Patient集約からサマリDTOを生成する。"""
        return cls(
            id=str(patient.id.value),
            patient_number=patient.patient_number.value,
            corporate_id=str(patient.corporate_id.value),
            last_name=patient.names.kanji.last_name.value,
            first_name=patient.names.kanji.first_name.value,
            last_name_kana=patient.names.kana.last_name.value,
            first_name_kana=patient.names.kana.first_name.value,
            birth_date=patient.birth_date.value.isoformat()
            if patient.birth_date
            else None,
            gender=unwrap(patient.gender),
            phone_number=unwrap(patient.phone_number),
            status=patient.status.value,
        )
