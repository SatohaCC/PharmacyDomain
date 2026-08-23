"""最後に記録した適用資格選択を候補として取得するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.reception.get_coverage_selection import CoverageSelectionRecordDto
from app.application.reception.reference import (
    CoverageValidityBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception import CoverageAppliedOn, CoverageSelectionRecordRepository
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class GetLastCoverageSelectionQuery:
    """最新選択候補取得の入力データ。"""

    corporate_id: str
    store_id: str
    patient_id: str
    applied_on: date


@dataclass(frozen=True, kw_only=True)
class LastCoverageSelectionCandidateDto:
    """最新履歴と今回の適用日における真正性。"""

    record: CoverageSelectionRecordDto
    is_still_valid: bool


class GetLastCoverageSelectionUseCase:
    """最新履歴を再検証済みの初期候補として返す。"""

    def __init__(
        self,
        repository: CoverageSelectionRecordRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
        coverage_validity: CoverageValidityBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference
        self._coverage_validity = coverage_validity

    async def execute(
        self,
        query: GetLastCoverageSelectionQuery,
    ) -> LastCoverageSelectionCandidateDto | None:
        """最新履歴があれば元IDと値を今回の適用日で再検証して返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_RECEPTION,
        )
        store_id = StoreId.parse(query.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        patient_id = PatientId.parse(query.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        record = await self._repository.get_latest(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
        )
        if record is None:
            return None
        is_still_valid = await self._coverage_validity.is_selection_valid(
            corporate_id=corporate_id,
            patient_id=patient_id,
            selection=record.selection,
            applied_on=CoverageAppliedOn(query.applied_on),
        )
        return LastCoverageSelectionCandidateDto(
            record=CoverageSelectionRecordDto.from_entity(record),
            is_still_valid=is_still_valid,
        )
