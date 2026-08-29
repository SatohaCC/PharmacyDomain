"""患者氏名変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.shared.person_name import PersonNames


@dataclass(frozen=True, kw_only=True)
class ChangePatientNamesCommand:
    """患者氏名変更の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class ChangePatientNamesUseCase:
    """患者氏名を変更するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangePatientNamesCommand) -> None:
        """法人境界を確認して患者氏名を変更する。"""
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
        names = PersonNames.create(
            last_name=command.last_name,
            first_name=command.first_name,
            last_name_kana=command.last_name_kana,
            first_name_kana=command.first_name_kana,
        )
        await self._repository.save(patient.change_names(names))
