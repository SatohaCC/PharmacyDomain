"""外部患者IDの登録ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
)
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)


@dataclass(frozen=True, kw_only=True)
class RegisterPatientExternalIdentifierCommand:
    """外部患者ID登録の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    system_name: str
    external_patient_id: str


@dataclass(frozen=True, kw_only=True)
class PatientExternalIdentifierDto:
    """外部患者ID対応付けの出力データ（DTO）。"""

    id: str
    corporate_id: str
    patient_id: str
    system_name: str
    external_patient_id: str
    is_active: bool

    @classmethod
    def from_entity(
        cls,
        identifier: PatientExternalIdentifier,
    ) -> PatientExternalIdentifierDto:
        """外部患者ID対応付けからDTOを生成する。"""
        return cls(
            id=str(identifier.id.value),
            corporate_id=str(identifier.corporate_id.value),
            patient_id=str(identifier.patient_id.value),
            system_name=identifier.system_name.value,
            external_patient_id=identifier.external_patient_id.value,
            is_active=identifier.is_active,
        )


class RegisterPatientExternalIdentifierUseCase:
    """外部患者IDを登録するアプリケーションサービス。"""

    def __init__(
        self,
        patient_repository: PatientRepository,
        identifier_repository: PatientExternalIdentifierRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._patient_repository = patient_repository
        self._identifier_repository = identifier_repository
        self._corporate_access = corporate_access

    async def execute(
        self,
        command: RegisterPatientExternalIdentifierCommand,
    ) -> PatientExternalIdentifierDto:
        """患者の存在と法人境界を確認して外部患者IDを登録する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        patient_id = PatientId.parse(command.patient_id)
        await load_patient_or_raise(
            self._patient_repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        system_name = ExternalSystemName(command.system_name)
        external_patient_id = ExternalPatientId(command.external_patient_id)
        existing = await self._identifier_repository.get_by_source(
            corporate_id=corporate_id,
            system_name=system_name,
            external_patient_id=external_patient_id,
        )
        if existing is not None:
            raise PatientExternalIdentifierAlreadyExistsError()

        identifier = PatientExternalIdentifier.create(
            corporate_id=corporate_id,
            patient_id=patient_id,
            system_name=system_name,
            external_patient_id=external_patient_id,
        )
        await self._identifier_repository.save(identifier)
        return PatientExternalIdentifierDto.from_entity(identifier)
