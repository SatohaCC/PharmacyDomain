"""適用資格選択履歴をApplication DTOへ変換する処理。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshotDto:
    """医療保険スナップショットの出力DTO。"""

    insurer_number: str
    insured_symbol: str
    insured_number: str
    insured_type: str
    branch_number: str | None
    benefit_ratio: int


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSnapshotDto:
    """公費スナップショットの出力DTO。"""

    priority: int
    payer_number: str
    recipient_number: str


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshotDto:
    """受付で固定した保険・公費組み合わせの出力DTO。"""

    insurance: InsuranceCoverageSnapshotDto | None
    public_expenses: tuple[PublicExpenseCoverageSnapshotDto, ...]

    @classmethod
    def from_value(cls, snapshot: CoverageSnapshot) -> CoverageSnapshotDto:
        """請求用スナップショットからDTOを生成する。"""
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
                benefit_ratio=insurance.benefit_ratio.value,
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
class CoverageSelectionRecordDto:
    """適用資格選択履歴の出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    applied_on: str
    source_coverage_ids: tuple[str, ...]
    snapshot: CoverageSnapshotDto
    recorded_at: str
    recorded_by: str

    @classmethod
    def from_entity(cls, record: CoverageSelectionRecord) -> CoverageSelectionRecordDto:
        """適用資格選択履歴からDTOを生成する。"""
        return cls(
            id=str(record.id.value),
            corporate_id=str(record.corporate_id.value),
            store_id=str(record.store_id.value),
            patient_id=str(record.patient_id.value),
            applied_on=record.applied_on.value.isoformat(),
            source_coverage_ids=tuple(
                str(item.value) for item in record.source_coverage_ids
            ),
            snapshot=CoverageSnapshotDto.from_value(record.snapshot),
            recorded_at=record.recorded_at.value.isoformat(),
            recorded_by=record.recorded_by.value,
        )
