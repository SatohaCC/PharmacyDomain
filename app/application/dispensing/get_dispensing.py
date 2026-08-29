"""調剤セッションをApplication DTOへ変換して取得する処理。

用量は ``Decimal`` なので**文字列で返す**（``float`` へ落とすと丸められる）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.support import load_dispensing_or_raise
from app.base.domain.dosage import DosageInstruction
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensedMedicine,
    DispensedRp,
    DispensingId,
    DispensingPrescriptionAudit,
    DispensingProcess,
    DispensingProcessRepository,
    DispensingVerification,
    QuantityAdjustment,
    SubstitutionDetail,
)


@dataclass(frozen=True, kw_only=True)
class SubstitutionDto:
    """代替調剤の出力DTO。"""

    category: str
    original_code_type: str
    original_code: str | None
    original_name: str
    reason: str | None

    @classmethod
    def from_value(cls, value: SubstitutionDetail) -> SubstitutionDto:
        """代替調剤の記録からDTOを生成する。"""
        return cls(
            category=value.category.value,
            original_code_type=value.original_identifier.code_type.value,
            original_code=(
                value.original_identifier.code.value
                if value.original_identifier.code is not None
                else None
            ),
            original_name=value.original_name.value,
            reason=value.reason.value if value.reason is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class QuantityAdjustmentDto:
    """減数調剤の出力DTO。"""

    prescribed_quantity: int
    reason: str

    @classmethod
    def from_value(cls, value: QuantityAdjustment) -> QuantityAdjustmentDto:
        """減数調剤の記録からDTOを生成する。"""
        return cls(
            prescribed_quantity=value.prescribed_quantity.value,
            reason=value.reason.value,
        )


@dataclass(frozen=True, kw_only=True)
class DosageInstructionDto:
    """用法の出力DTO。"""

    code_type: str
    name: str
    code: str | None
    daily_frequency: int | None

    @classmethod
    def from_value(cls, value: DosageInstruction) -> DosageInstructionDto:
        """用法からDTOを生成する。"""
        return cls(
            code_type=value.code_type.value,
            name=value.name.value,
            code=value.code.value if value.code is not None else None,
            daily_frequency=(
                value.daily_frequency.value
                if value.daily_frequency is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class DispensedMedicineDto:
    """調剤した薬品1明細の出力DTO。"""

    line_number: int
    code_type: str
    code: str | None
    name: str
    amount: str
    unit: str
    substitution: SubstitutionDto | None
    preparations: tuple[str, ...]
    public_expense_first: bool
    public_expense_second: bool
    public_expense_third: bool
    public_expense_special: bool

    @classmethod
    def from_value(cls, value: DispensedMedicine) -> DispensedMedicineDto:
        """調剤した薬品からDTOを生成する。"""
        burden = value.public_expense_burden
        return cls(
            line_number=value.line_number.value,
            code_type=value.identifier.code_type.value,
            code=(
                value.identifier.code.value
                if value.identifier.code is not None
                else None
            ),
            name=value.name.value,
            amount=str(value.amount.value),
            unit=value.unit.value,
            substitution=(
                SubstitutionDto.from_value(value.substitution)
                if value.substitution is not None
                else None
            ),
            preparations=tuple(item.value for item in value.preparations),
            public_expense_first=burden is not None and burden.first,
            public_expense_second=burden is not None and burden.second,
            public_expense_third=burden is not None and burden.third,
            public_expense_special=burden is not None and burden.special,
        )


@dataclass(frozen=True, kw_only=True)
class DispensedRpDto:
    """調剤した剤（Rp）の出力DTO。"""

    rp_number: int
    category: str
    quantity: int
    dosage_instruction: DosageInstructionDto
    medicines: tuple[DispensedMedicineDto, ...]
    quantity_adjustment: QuantityAdjustmentDto | None

    @classmethod
    def from_value(cls, value: DispensedRp) -> DispensedRpDto:
        """調剤した剤からDTOを生成する。"""
        return cls(
            rp_number=value.rp_number.value,
            category=value.category.value,
            quantity=value.quantity.value,
            dosage_instruction=DosageInstructionDto.from_value(
                value.dosage_instruction
            ),
            medicines=tuple(
                DispensedMedicineDto.from_value(item) for item in value.medicines
            ),
            quantity_adjustment=(
                QuantityAdjustmentDto.from_value(value.quantity_adjustment)
                if value.quantity_adjustment is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class DispensingAuditDto:
    """処方鑑査の出力DTO。"""

    auditor_id: str
    audited_at: str
    has_issues: bool
    notes: str | None

    @classmethod
    def from_value(cls, value: DispensingPrescriptionAudit) -> DispensingAuditDto:
        """処方鑑査の記録からDTOを生成する。"""
        return cls(
            auditor_id=str(value.auditor_id.value),
            audited_at=value.audited_at.value.isoformat(),
            has_issues=value.has_issues,
            notes=value.notes.value if value.notes is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class DispensingVerificationDto:
    """最終鑑査の出力DTO。"""

    verifier_id: str
    verified_at: str
    result: str
    notes: str | None

    @classmethod
    def from_value(cls, value: DispensingVerification) -> DispensingVerificationDto:
        """最終鑑査の記録からDTOを生成する。"""
        return cls(
            verifier_id=str(value.verifier_id.value),
            verified_at=value.verified_at.value.isoformat(),
            result=value.result.value,
            notes=value.notes.value if value.notes is not None else None,
        )


@dataclass(frozen=True, kw_only=True)
class DispensingProcessDto:
    """調剤セッションの出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    prescription_id: str
    iteration: int
    dispensed_date: str
    dispenser_id: str
    started_at: str
    status: str
    completion_type: str
    split_reason: str | None
    next_dispensing_date: str | None
    dispensed_rps: tuple[DispensedRpDto, ...]
    audit: DispensingAuditDto | None
    verification: DispensingVerificationDto | None
    cancellation_reason: str | None

    @classmethod
    def from_entity(cls, process: DispensingProcess) -> DispensingProcessDto:
        """調剤セッション集約からDTOを生成する。"""
        return cls(
            id=str(process.id.value),
            corporate_id=str(process.corporate_id.value),
            store_id=str(process.store_id.value),
            patient_id=str(process.patient_id.value),
            prescription_id=str(process.prescription_id.value),
            iteration=process.iteration.value,
            dispensed_date=process.dispensed_date.value.isoformat(),
            dispenser_id=str(process.dispenser_id.value),
            started_at=process.started_at.value.isoformat(),
            status=process.status.value,
            completion_type=process.completion_type.value,
            split_reason=(
                process.split_reason.value if process.split_reason is not None else None
            ),
            next_dispensing_date=(
                process.next_dispensing_date.value.isoformat()
                if process.next_dispensing_date is not None
                else None
            ),
            dispensed_rps=tuple(
                DispensedRpDto.from_value(rp) for rp in process.dispensed_rps
            ),
            audit=(
                DispensingAuditDto.from_value(process.audit)
                if process.audit is not None
                else None
            ),
            verification=(
                DispensingVerificationDto.from_value(process.verification)
                if process.verification is not None
                else None
            ),
            cancellation_reason=(
                process.cancellation_reason.value
                if process.cancellation_reason is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class GetDispensingQuery:
    """調剤セッション取得の入力データ。"""

    corporate_id: str
    dispensing_id: str


class GetDispensingUseCase:
    """法人境界を確認して調剤セッションを取得する。"""

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetDispensingQuery) -> DispensingProcessDto:
        """指定法人の調剤セッションをDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_DISPENSING,
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(query.dispensing_id),
        )
        return DispensingProcessDto.from_entity(process)
