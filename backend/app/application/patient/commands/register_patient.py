"""Applicationのregister_patientを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.optional_conversion import build_optional
from app.application.patient.commands.models import RegisterPatientCommand
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import Patient
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import (
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.repositories import PatientRepository
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)


class RegisterPatientUseCase:
    """患者を新規登録するアプリケーションサービス。"""

    def __init__(
        self, repository: PatientRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterPatientCommand) -> PatientId:
        """患者を登録し、採番された患者IDを返す。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_PATIENT
        )
        names = PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart(command.last_name),
                first_name=PersonNamePart(command.first_name),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart(command.last_name_kana),
                first_name=PersonNameKanaPart(command.first_name_kana),
            ),
        )
        birth_date = (
            PatientBirthDate(command.birth_date) if command.birth_date else None
        )
        patient_number = await self._repository.allocate_patient_number(corporate_id)
        patient = Patient(
            id=PatientId.generate(),
            corporate_id=corporate_id,
            names=names,
            patient_number=patient_number,
            birth_date=birth_date,
            gender=build_optional(command.gender, PatientGenderCode),
            postal_code=build_optional(command.postal_code, PatientPostalCode),
            address=build_optional(command.address, PatientAddress),
            phone_number=build_optional(command.phone_number, PatientPhoneNumber),
        )
        await self._repository.save(patient)
        return patient.id
