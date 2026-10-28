"""Applicationのregister_patient_external_identifierを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.patient.commands.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.commands.models import (
    RegisterPatientExternalIdentifierCommand,
)
from app.application.patient.commands.services.support import load_patient_or_raise
from app.application.patient.interfaces.references import PatientStoreReferenceBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import PatientExternalIdentifier
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.identifiers import PatientExternalIdentifierId, PatientId
from app.domain.patient.primitives import ExternalPatientId, ExternalSystemName
from app.domain.patient.repositories import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)
from app.domain.store.identifiers import StoreId


class RegisterPatientExternalIdentifierUseCase:
    """外部患者IDを登録するアプリケーションサービス。"""

    def __init__(
        self,
        patient_repository: PatientRepository,
        identifier_repository: PatientExternalIdentifierRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: PatientStoreReferenceBoundary | None = None,
    ) -> None:
        self._patient_repository = patient_repository
        self._identifier_repository = identifier_repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference

    async def execute(
        self, command: RegisterPatientExternalIdentifierCommand
    ) -> PatientExternalIdentifierDto:
        """患者の存在と法人境界を確認して外部患者IDを登録する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_PATIENT
        )
        patient_id = PatientId.parse(command.patient_id)
        await load_patient_or_raise(
            self._patient_repository, corporate_id=corporate_id, patient_id=patient_id
        )
        system_name = ExternalSystemName(command.system_name)
        external_patient_id = ExternalPatientId(command.external_patient_id)
        store_id = StoreId.parse(command.store_id) if command.store_id else None
        if store_id is not None and self._store_reference is not None:
            await self._store_reference.require_exists(
                corporate_id=corporate_id, store_id=store_id
            )
        existing = await self._identifier_repository.get_active_by_source(
            corporate_id=corporate_id,
            store_id=store_id,
            system_name=system_name,
            external_patient_id=external_patient_id,
        )
        if existing is not None:
            raise PatientExternalIdentifierAlreadyExistsError()
        identifier = PatientExternalIdentifier(
            id=PatientExternalIdentifierId.generate(),
            corporate_id=corporate_id,
            patient_id=patient_id,
            system_name=system_name,
            external_patient_id=external_patient_id,
            store_id=store_id,
        )
        await self._identifier_repository.save(identifier)
        return PatientExternalIdentifierDto.from_entity(identifier)
