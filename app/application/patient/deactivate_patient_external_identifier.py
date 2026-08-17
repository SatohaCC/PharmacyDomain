"""外部患者ID対応付けの無効化ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.exceptions import PatientExternalIdentifierNotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientExternalIdentifierId
from app.domain.patient.repository import PatientExternalIdentifierRepository


@dataclass(frozen=True, kw_only=True)
class DeactivatePatientExternalIdentifierCommand:
    """外部患者ID対応付け無効化の入力データ（DTO）。"""

    corporate_id: str
    identifier_id: str


class DeactivatePatientExternalIdentifierUseCase:
    """外部患者ID対応付けを無効化する。"""

    def __init__(
        self,
        repository: PatientExternalIdentifierRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: DeactivatePatientExternalIdentifierCommand
    ) -> None:
        """法人境界を確認して外部患者ID対応付けを無効化する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        identifier_id = PatientExternalIdentifierId.parse(command.identifier_id)
        identifier = await self._repository.get(
            corporate_id=corporate_id,
            identifier_id=identifier_id,
        )
        if identifier is None:
            raise PatientExternalIdentifierNotFoundError()
        await self._repository.save(identifier.deactivate())
