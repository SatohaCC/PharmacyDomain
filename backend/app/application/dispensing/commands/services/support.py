"""Applicationのsupportを定義する。"""

from __future__ import annotations

from decimal import Decimal

from app.application.access_control.boundary_models import (
    ActorContext,
    ResolvedActorContext,
)
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import build_optional
from app.application.dispensing.commands.models import (
    DispensedMedicineInput,
    DispensedRpInput,
    QuantityAdjustmentInput,
    SubstitutionInput,
)
from app.application.dispensing.errors import DispensingNotFoundError
from app.application.dispensing.values import parse_enum, required_text
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.primitives import (
    DailyFrequency,
    DispensingQuantity,
    DosageAmount,
    DosageCode,
    DosageCodeType,
    DosageFormCategory,
    DosageName,
    InquiryNumber,
    MedicineCode,
    MedicineCodeType,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PreparationMethod,
    QuantityAdjustmentReason,
    RpNumber,
    SubstitutionCategory,
    SubstitutionReason,
)
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.dispensing.value_objects import (
    DispensedMedicine,
    DispensedRp,
    DosageInstruction,
    MedicineIdentifier,
    QuantityAdjustment,
    SubstitutionDetail,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.identifiers import StaffId


def resolve_acting_staff_id(
    actor: ActorContext, requested_staff_id: str | None = None
) -> StaffId:
    """信頼済みActorから実施スタッフIDを解決し、他人指定のなりすましを拒否する。"""
    if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
        raise AuthorizationError("調剤業務にはスタッフを特定できるActorが必要です。")
    if requested_staff_id is not None:
        parsed = StaffId.parse(requested_staff_id)
        if parsed != actor.staff_id:
            raise AuthorizationError(
                "ログイン中のスタッフ以外のIDを実施者として指定することはできません。"
            )
    return actor.staff_id


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    """入力文字列を ``Decimal`` へ変換する。``float`` を経由しない。"""
    try:
        return Decimal(raw.strip())
    except (ArithmeticError, ValueError) as exc:
        raise DomainValidationError(f"{field_name}は数値で指定してください。") from exc


def _build_substitution(source: SubstitutionInput) -> SubstitutionDetail:
    """代替調剤の記録を構成する。"""
    return SubstitutionDetail(
        category=parse_enum(SubstitutionCategory, source.category, "代替調剤種別"),
        original_identifier=MedicineIdentifier(
            code_type=parse_enum(
                MedicineCodeType, source.original_code_type, "変更前の薬品コード種別"
            ),
            code=build_optional(source.original_code, MedicineCode),
        ),
        original_name=MedicineName(
            required_text(source.original_name, "変更前の薬品名称")
        ),
        reason=build_optional(source.reason, SubstitutionReason),
        inquiry_number=InquiryNumber(source.inquiry_number)
        if source.inquiry_number is not None
        else None,
    )


def _build_quantity_adjustment(source: QuantityAdjustmentInput) -> QuantityAdjustment:
    """減数調剤の記録を構成する。"""
    return QuantityAdjustment(
        prescribed_quantity=DispensingQuantity(source.prescribed_quantity),
        reason=parse_enum(QuantityAdjustmentReason, source.reason, "数量調整の理由"),
        inquiry_number=InquiryNumber(source.inquiry_number)
        if source.inquiry_number is not None
        else None,
    )


def _build_public_expense_burden(
    source: DispensedMedicineInput,
) -> PublicExpenseBurden | None:
    """公費負担区分を構成する。負担がどれも無ければ持たせない。"""
    burden = PublicExpenseBurden(
        first=source.public_expense_first,
        second=source.public_expense_second,
        third=source.public_expense_third,
        special=source.public_expense_special,
    )
    return burden if burden.bears_any else None


def _build_medicine(source: DispensedMedicineInput) -> DispensedMedicine:
    """調剤した薬品の1明細を構成する。"""
    return DispensedMedicine(
        line_number=MedicineLineNumber(source.line_number),
        identifier=MedicineIdentifier(
            code_type=parse_enum(MedicineCodeType, source.code_type, "薬品コード種別"),
            code=build_optional(source.code, MedicineCode),
        ),
        name=MedicineName(required_text(source.name, "薬品名称")),
        amount=DosageAmount(_parse_decimal(source.amount, "分量")),
        unit=MedicineUnit(required_text(source.unit, "単位名")),
        substitution=_build_substitution(source.substitution)
        if source.substitution is not None
        else None,
        preparations=tuple(
            parse_enum(PreparationMethod, item, "調製方法")
            for item in source.preparations
        ),
        public_expense_burden=_build_public_expense_burden(source),
    )


def _build_dosage_instruction(source: DispensedRpInput) -> DosageInstruction:
    """用法を構成する。"""
    return DosageInstruction(
        code_type=parse_enum(DosageCodeType, source.dosage_code_type, "用法コード種別"),
        name=DosageName(required_text(source.dosage_name, "用法名称")),
        code=build_optional(source.dosage_code, DosageCode),
        daily_frequency=DailyFrequency(source.daily_frequency)
        if source.daily_frequency is not None
        else None,
    )


def _build_rp(source: DispensedRpInput) -> DispensedRp:
    """調剤した剤（Rp）を構成する。"""
    return DispensedRp(
        rp_number=RpNumber(source.rp_number),
        category=parse_enum(DosageFormCategory, source.category, "剤形区分"),
        quantity=DispensingQuantity(source.quantity),
        dosage_instruction=_build_dosage_instruction(source),
        medicines=tuple(_build_medicine(item) for item in source.medicines),
        quantity_adjustment=_build_quantity_adjustment(source.quantity_adjustment)
        if source.quantity_adjustment is not None
        else None,
    )


def build_dispensed_rps(
    sources: tuple[DispensedRpInput, ...],
) -> tuple[DispensedRp, ...]:
    """調剤した剤（Rp）の一覧を構成する。"""
    return tuple(_build_rp(source) for source in sources)


async def load_dispensing_or_raise(
    repository: DispensingProcessRepository,
    *,
    corporate_id: CorporateId,
    dispensing_id: DispensingId,
) -> DispensingProcess:
    """指定法人の調剤セッションを取得し、存在しなければ404相当を送出する。"""
    process = await repository.get(
        corporate_id=corporate_id, dispensing_id=dispensing_id
    )
    if process is None:
        raise DispensingNotFoundError()
    return process
