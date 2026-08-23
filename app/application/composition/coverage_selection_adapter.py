"""Coverage台帳とReception境界を接続する実アダプタ。"""

from __future__ import annotations

from app.application.reception.exceptions import ReceptionCoverageSelectionError
from app.application.reception.reference import CoverageSelectionMaterial
from app.base.domain.exceptions import DomainError
from app.domain.claim import (
    ClaimCoverageBenefitRatio,
    ClaimCoverageBranchNumber,
    ClaimCoverageCode,
    ClaimCoverageInsuredType,
    ClaimCoveragePriority,
    ClaimCoverageSymbol,
    ClaimInsurerNumber,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    CoverageSnapshot,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import (
    CoverageCombination,
    CoverageSelectionService,
    PatientCoverageId,
    PatientCoverageRepository,
)
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import CoverageAppliedOn, SourceCoverageId


class CoverageSelectionAdapter:
    """元資格IDを検証し、正規化ID列と請求Snapshotを同時に構築する。"""

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
    ) -> CoverageSelectionMaterial:
        """入力IDを検証し、存在を漏らさない選択エラーへ畳んで返す。"""
        try:
            requested_ids = tuple(
                PatientCoverageId.parse(raw_id) for raw_id in coverage_ids
            )
            return await self._build_material(
                corporate_id=corporate_id,
                patient_id=patient_id,
                requested_ids=requested_ids,
                applied_on=applied_on,
            )
        except ReceptionCoverageSelectionError:
            raise
        except DomainError as exc:
            raise ReceptionCoverageSelectionError() from exc

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        source_coverage_ids: tuple[SourceCoverageId, ...],
        snapshot: CoverageSnapshot,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ元IDから同じ正規化ID列とSnapshotを再構築できるか返す。"""
        try:
            requested_ids = tuple(
                PatientCoverageId(item.value) for item in source_coverage_ids
            )
            rebuilt = await self._build_material(
                corporate_id=corporate_id,
                patient_id=patient_id,
                requested_ids=requested_ids,
                applied_on=applied_on,
            )
        except DomainError, ReceptionCoverageSelectionError:
            return False
        return (
            rebuilt.source_coverage_ids == source_coverage_ids
            and rebuilt.snapshot == snapshot
        )

    async def _build_material(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        requested_ids: tuple[PatientCoverageId, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelectionMaterial:
        """指定IDだけをロードし、Domainの選択投影から境界DTOを作る。"""
        coverages = []
        for coverage_id in requested_ids:
            coverage = await self._repository.get(
                corporate_id=corporate_id,
                coverage_id=coverage_id,
            )
            if coverage is None:
                raise ReceptionCoverageSelectionError()
            coverages.append(coverage)

        combination = self._selection_service.build_selection(
            coverages=coverages,
            requested_ids=requested_ids,
            corporate_id=corporate_id,
            patient_id=patient_id,
            applied_on=applied_on.value,
        )
        return CoverageSelectionMaterial(
            source_coverage_ids=tuple(
                SourceCoverageId(item.value) for item in combination.source_coverage_ids
            ),
            snapshot=self._to_snapshot(combination),
        )

    @staticmethod
    def _to_snapshot(combination: CoverageCombination) -> CoverageSnapshot:
        """Coverageの選択投影をClaim専用プリミティブへコピーする。"""
        selected_insurance = combination.insurance
        insurance = None
        if selected_insurance is not None:
            details = selected_insurance.details
            insurance = InsuranceCoverageSnapshot(
                insurer_number=ClaimInsurerNumber(details.insurer_number.value),
                insured_symbol=ClaimCoverageSymbol(details.insured_symbol.value),
                insured_number=ClaimCoverageCode(details.insured_number.value),
                insured_type=ClaimCoverageInsuredType(details.insured_type.value),
                benefit_ratio=ClaimCoverageBenefitRatio(details.benefit_ratio.value),
                branch_number=(
                    ClaimCoverageBranchNumber(details.branch_number.value)
                    if details.branch_number is not None
                    else None
                ),
            )

        public_expenses = tuple(
            PublicExpenseCoverageSnapshot(
                priority=ClaimCoveragePriority(item.priority.value),
                payer_number=ClaimPublicPayerNumber(item.details.payer_number.value),
                recipient_number=ClaimPublicRecipientNumber(
                    item.details.recipient_number.value
                ),
            )
            for item in combination.public_expenses
        )
        return CoverageSnapshot(
            insurance=insurance,
            public_expenses=public_expenses,
        )
