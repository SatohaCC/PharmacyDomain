"""患者新規登録ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientBirthDate, PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.shared.person_name import PersonNames


@dataclass(frozen=True, kw_only=True)
class RegisterPatientCommand:
    """患者登録に必要な入力データ（DTO）。"""

    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: date | None = None


class RegisterPatientUseCase:
    """患者を新規登録するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterPatientCommand) -> PatientId:
        """患者を登録し、採番された患者IDを返す。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )

        names = PersonNames.create(
            last_name=command.last_name,
            first_name=command.first_name,
            last_name_kana=command.last_name_kana,
            first_name_kana=command.first_name_kana,
        )
        birth_date = (
            PatientBirthDate(command.birth_date) if command.birth_date else None
        )
        patient_number = await self._repository.allocate_patient_number(corporate_id)
        patient = Patient.create(
            corporate_id=corporate_id,
            names=names,
            patient_number=patient_number,
            birth_date=birth_date,
        )
        await self._repository.save(patient)
        return patient.id
