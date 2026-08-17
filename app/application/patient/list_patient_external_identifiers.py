"""患者に紐付く外部患者ID一覧の取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)


@dataclass(frozen=True, kw_only=True)
class ListPatientExternalIdentifiersQuery:
    """患者の外部患者ID一覧取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str


class ListPatientExternalIdentifiersUseCase:
    """患者に紐付く外部患者ID一覧を取得する。"""

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
        query: ListPatientExternalIdentifiersQuery,
    ) -> list[PatientExternalIdentifierDto]:
        """法人境界と患者の存在を確認して外部患者ID一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT,
        )
        patient_id = PatientId.parse(query.patient_id)
        await load_patient_or_raise(
            self._patient_repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        identifiers = await self._identifier_repository.list_by_patient(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        return [PatientExternalIdentifierDto.from_entity(item) for item in identifiers]
