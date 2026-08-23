"""適用資格選択履歴をApplication DTOへ変換する処理。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.reception.coverage_selection import CoverageSelection
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSelectionDto:
    """医療保険枠の出力DTO。選択元IDと請求固定値を束ねたまま返す。"""

    source_coverage_id: str
    insurer_number: str
    insured_symbol: str
    insured_number: str
    insured_type: str
    branch_number: str | None
    benefit_ratio: int


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSelectionDto:
    """公費枠の出力DTO。選択元IDと請求固定値を束ねたまま返す。"""

    source_coverage_id: str
    priority: int
    payer_number: str
    recipient_number: str


@dataclass(frozen=True, kw_only=True)
class CoverageSelectionDto:
    """受付で固定した保険・公費の選択の出力DTO。

    ドメイン側と同じ枠構造で返す。平坦な元ID列を併記すると、消費側が位置で
    値と対応づける余地が戻ってしまうため持たせない。
    """

    insurance: InsuranceCoverageSelectionDto | None
    public_expenses: tuple[PublicExpenseCoverageSelectionDto, ...]

    @classmethod
    def from_value(cls, selection: CoverageSelection) -> CoverageSelectionDto:
        """枠ごとの選択からDTOを生成する。"""
        insurance = selection.insurance
        insurance_dto = (
            InsuranceCoverageSelectionDto(
                source_coverage_id=str(insurance.source_coverage_id.value),
                insurer_number=insurance.values.insurer_number.value,
                insured_symbol=insurance.values.insured_symbol.value,
                insured_number=insurance.values.insured_number.value,
                insured_type=insurance.values.insured_type.value,
                branch_number=(
                    insurance.values.branch_number.value
                    if insurance.values.branch_number is not None
                    else None
                ),
                benefit_ratio=insurance.values.benefit_ratio.value,
            )
            if insurance is not None
            else None
        )
        return cls(
            insurance=insurance_dto,
            public_expenses=tuple(
                PublicExpenseCoverageSelectionDto(
                    source_coverage_id=str(item.source_coverage_id.value),
                    priority=item.values.priority.value,
                    payer_number=item.values.payer_number.value,
                    recipient_number=item.values.recipient_number.value,
                )
                for item in selection.public_expenses
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
    selection: CoverageSelectionDto
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
            selection=CoverageSelectionDto.from_value(record.selection),
            recorded_at=record.recorded_at.value.isoformat(),
            recorded_by=record.recorded_by.value,
        )
