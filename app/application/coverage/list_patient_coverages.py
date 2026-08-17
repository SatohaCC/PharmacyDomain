"""患者資格一覧ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.coverage.get_patient_coverage import PatientCoverageDto
from app.application.coverage.reference import PatientReferenceBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, kw_only=True)
class ListPatientCoveragesQuery:
    """患者資格一覧取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str


class ListPatientCoveragesUseCase:
    """患者に紐付く資格一覧を取得する。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        patient_reference: PatientReferenceBoundary,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._patient_reference = patient_reference
        self._corporate_access = corporate_access

    async def execute(
        self,
        query: ListPatientCoveragesQuery,
    ) -> list[PatientCoverageDto]:
        """法人・患者の存在を確認して資格一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_COVERAGE,
        )
        patient_id = PatientId.parse(query.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        coverages = await self._repository.list_by_patient(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        return [PatientCoverageDto.from_entity(item) for item in coverages]
