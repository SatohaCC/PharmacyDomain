"""適用資格利用履歴をApplication DTOへ変換する処理。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.claim.coverage_usage import CoverageUsage


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshotDto:
    """医療保険スナップショットの出力DTO。"""

    insurer_number: str
    insured_symbol: str
    insured_number: str
    insured_type: str
    branch_number: str | None
    benefit_ratio: int | None


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSnapshotDto:
    """公費スナップショットの出力DTO。"""

    priority: int
    payer_number: str
    recipient_number: str


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshotDto:
    """請求時点の保険・公費組み合わせの出力DTO。"""

    insurance: InsuranceCoverageSnapshotDto | None
    public_expenses: tuple[PublicExpenseCoverageSnapshotDto, ...]

    @classmethod
    def from_value(cls, snapshot: CoverageSnapshot) -> CoverageSnapshotDto:
        """請求側スナップショットからDTOを生成する。"""
        insurance = snapshot.insurance
        insurance_dto = (
            InsuranceCoverageSnapshotDto(
                insurer_number=insurance.insurer_number.value,
                insured_symbol=insurance.insured_symbol.value,
                insured_number=insurance.insured_number.value,
                insured_type=insurance.insured_type.value,
                branch_number=(
                    insurance.branch_number.value
                    if insurance.branch_number is not None
                    else None
                ),
                benefit_ratio=(
                    insurance.benefit_ratio.value
                    if insurance.benefit_ratio is not None
                    else None
                ),
            )
            if insurance is not None
            else None
        )
        return cls(
            insurance=insurance_dto,
            public_expenses=tuple(
                PublicExpenseCoverageSnapshotDto(
                    priority=item.priority.value,
                    payer_number=item.payer_number.value,
                    recipient_number=item.recipient_number.value,
                )
                for item in snapshot.public_expenses
            ),
        )


@dataclass(frozen=True, kw_only=True)
class CoverageUsageDto:
    """適用資格利用履歴の出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    applied_at: str
    snapshot: CoverageSnapshotDto

    @classmethod
    def from_entity(cls, usage: CoverageUsage) -> CoverageUsageDto:
        """適用資格利用履歴集約からDTOを生成する。"""
        return cls(
            id=str(usage.id.value),
            corporate_id=str(usage.corporate_id.value),
            store_id=str(usage.store_id.value),
            patient_id=str(usage.patient_id.value),
            applied_at=usage.applied_at.value.isoformat(),
            snapshot=CoverageSnapshotDto.from_value(usage.snapshot),
        )
