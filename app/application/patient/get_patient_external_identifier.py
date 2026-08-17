"""外部患者ID対応付けの取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.exceptions import PatientExternalIdentifierNotFoundError
from app.application.patient.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientExternalIdentifierId
from app.domain.patient.repository import PatientExternalIdentifierRepository


@dataclass(frozen=True, kw_only=True)
class GetPatientExternalIdentifierQuery:
    """外部患者ID対応付け取得の入力データ（DTO）。"""

    corporate_id: str
    identifier_id: str


class GetPatientExternalIdentifierUseCase:
    """外部患者ID対応付けを取得するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientExternalIdentifierRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self,
        query: GetPatientExternalIdentifierQuery,
    ) -> PatientExternalIdentifierDto:
        """法人境界を確認して外部患者ID対応付けをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT,
        )
        identifier_id = PatientExternalIdentifierId.parse(query.identifier_id)
        identifier = await self._repository.get(
            corporate_id=corporate_id,
            identifier_id=identifier_id,
        )
        if identifier is None:
            raise PatientExternalIdentifierNotFoundError()
        return PatientExternalIdentifierDto.from_entity(identifier)
