"""薬歴表示から患者の現行プロフィールを読む実アダプタ。"""

from __future__ import annotations

from app.application.common.optional_conversion import unwrap
from app.application.medication_history.get_medication_history_view import (
    CurrentPatientProfileBoundary,
    MedicationHistoryPatientProfileDto,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


class MedicationHistoryPatientProfileAdapter(CurrentPatientProfileBoundary):
    """Patient Repositoryを薬歴の現行プロフィールBoundaryへ変換する。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def get_current_profile(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> MedicationHistoryPatientProfileDto | None:
        """法人境界内の患者プロフィールを表示用DTOにする。"""
        patient = await self._repository.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            return None
        return MedicationHistoryPatientProfileDto(
            last_name=patient.names.kanji.last_name.value,
            first_name=patient.names.kanji.first_name.value,
            last_name_kana=patient.names.kana.last_name.value,
            first_name_kana=patient.names.kana.first_name.value,
            birth_date=(
                patient.birth_date.value.isoformat()
                if patient.birth_date is not None
                else None
            ),
            gender=unwrap(patient.gender),
            postal_code=unwrap(patient.postal_code),
            address=unwrap(patient.address),
            phone_number=unwrap(patient.phone_number),
        )
