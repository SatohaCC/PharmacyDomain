"""Coverage台帳とReception境界を接続する実アダプタ。"""

from __future__ import annotations

from app.application.reception.exceptions import ReceptionCoverageSelectionError
from app.application.reception.reference import (
    CoverageSelectionBoundary,
    CoverageValidityBoundary,
)
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
from app.domain.foundation.exceptions import DomainError
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection import (
    CoverageSelection,
    SelectedInsuranceSource,
    SelectedPublicExpenseSource,
)
from app.domain.reception.primitives import CoverageAppliedOn, SourceCoverageId


class CoverageSelectionAdapter(CoverageSelectionBoundary, CoverageValidityBoundary):
    """元資格IDを検証し、枠ごとにIDと請求固定値を束ねた選択を構築する。

    2つのProtocolを明示継承するのは、``tools/check_fake_conformance.py`` に
    上書き漏れを検出させるためである。構造的部分型のままだと、Protocol側に
    メンバが増えても実アダプタは静かに取り残される。
    """

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
        """入力IDを検証し、存在を漏らさない選択エラーへ畳んで返す。"""
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
        except ReceptionCoverageSelectionError:
            raise
        except DomainError as exc:
            raise ReceptionCoverageSelectionError() from exc

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        selection: CoverageSelection,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ元IDから同じ選択を再構築できるか返す。

        枠がIDと値を束ねているので、照合は値等価の比較1本で足りる。
        """
        try:
            requested_ids = tuple(
                PatientCoverageId(item.value) for item in selection.source_coverage_ids
            )
            rebuilt = await self._build_selection(
                corporate_id=corporate_id,
                patient_id=patient_id,
                requested_ids=requested_ids,
                applied_on=applied_on,
            )
        except DomainError, ReceptionCoverageSelectionError:
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
                raise ReceptionCoverageSelectionError()
            coverages.append(coverage)

        combination = self._selection_service.build_selection(
            coverages=coverages,
            requested_ids=requested_ids,
            corporate_id=corporate_id,
            patient_id=patient_id,
            applied_on=applied_on.value,
        )
        return self._to_selection(combination)

    @staticmethod
    def _to_selection(combination: CoverageCombination) -> CoverageSelection:
        """Coverageの選択投影を、枠ごとにClaim専用プリミティブへ写す。"""
        selected_insurance = combination.insurance
        insurance = None
        if selected_insurance is not None:
            details = selected_insurance.details
            insurance = SelectedInsuranceSource(
                source_coverage_id=SourceCoverageId(
                    selected_insurance.source_coverage_id.value
                ),
                values=InsuranceCoverageSnapshot(
                    insurer_number=ClaimInsurerNumber(details.insurer_number.value),
                    insured_symbol=ClaimCoverageSymbol(details.insured_symbol.value),
                    insured_number=ClaimCoverageCode(details.insured_number.value),
                    insured_type=ClaimCoverageInsuredType(details.insured_type.value),
                    benefit_ratio=ClaimCoverageBenefitRatio(
                        details.benefit_ratio.value
                    ),
                    branch_number=(
                        ClaimCoverageBranchNumber(details.branch_number.value)
                        if details.branch_number is not None
                        else None
                    ),
                ),
            )

        public_expenses = tuple(
            SelectedPublicExpenseSource(
                source_coverage_id=SourceCoverageId(item.source_coverage_id.value),
                values=PublicExpenseCoverageSnapshot(
                    priority=ClaimCoveragePriority(item.priority.value),
                    payer_number=ClaimPublicPayerNumber(
                        item.details.payer_number.value
                    ),
                    recipient_number=ClaimPublicRecipientNumber(
                        item.details.recipient_number.value
                    ),
                ),
            )
            for item in combination.public_expenses
        )
        return CoverageSelection(
            insurance=insurance,
            public_expenses=public_expenses,
        )
