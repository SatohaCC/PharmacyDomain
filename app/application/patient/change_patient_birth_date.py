"""患者生年月日変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientBirthDate, PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class ChangePatientBirthDateCommand:
    """患者生年月日変更の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    birth_date: date | None


class ChangePatientBirthDateUseCase:
    """患者の生年月日を変更するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangePatientBirthDateCommand) -> None:
        """法人境界を確認して患者の生年月日を変更する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        patient_id = PatientId.parse(command.patient_id)
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        birth_date = (
            PatientBirthDate(command.birth_date) if command.birth_date else None
        )
        await self._repository.save(patient.change_birth_date(birth_date))
