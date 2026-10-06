"""資格台帳から適用選択を構築・再検証するApplication境界。"""

from __future__ import annotations

from app.application.coverage.exceptions import CoverageSelectionError
from app.application.coverage.reference import (
    CoverageSelectionBoundary,
    CoverageValidityBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.combination import CoverageSelectionService
from app.domain.coverage.coverage_selection import CoverageSelection
from app.domain.coverage.primitives import CoverageAppliedOn, PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId


class CoverageSelectionBuilder(CoverageSelectionBoundary, CoverageValidityBoundary):
    """元資格IDを台帳で解決し、同じ規則で選択を構築・再検証する。"""

    def __init__(
        self,
        repository: PatientCoverageRepository,
        selection_service: CoverageSelectionService,
    ) -> None:
        self._repository = repository
        self._selection_service = selection_service

    async def build_selection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelection:
        """入力IDを台帳で解決し、存在を区別しない選択エラーへ畳む。"""
        try:
            requested_ids = tuple(
                PatientCoverageId.parse(raw_id) for raw_id in coverage_ids
            )
            return await self._build_selection(
                corporate_id=corporate_id,
                patient_id=patient_id,
                requested_ids=requested_ids,
                applied_on=applied_on,
            )
        except CoverageSelectionError:
            raise
        except DomainError as exc:
            raise CoverageSelectionError() from exc

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        selection: CoverageSelection,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ元資格IDから同じ固定値を再構築できるか返す。"""
        try:
            requested_ids = selection.source_coverage_ids
            rebuilt = await self._build_selection(
                corporate_id=corporate_id,
                patient_id=patient_id,
                requested_ids=requested_ids,
                applied_on=applied_on,
            )
        except CoverageSelectionError, DomainError:
            return False
        return rebuilt == selection

    async def _build_selection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        requested_ids: tuple[PatientCoverageId, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelection:
        """指定IDだけをロードし、Domainの選択投影から枠構造を作る。"""
        coverages = []
        for coverage_id in requested_ids:
            coverage = await self._repository.get(
                corporate_id=corporate_id,
                coverage_id=coverage_id,
            )
            if coverage is None:
                raise CoverageSelectionError()
            coverages.append(coverage)

        combination = self._selection_service.build_selection(
            coverages=coverages,
            requested_ids=requested_ids,
            corporate_id=corporate_id,
            patient_id=patient_id,
            applied_on=applied_on.value,
        )
        return CoverageSelection.from_combination(combination)
