"""Dispensingユースケース間で共有する入力変換処理。

``to_optional_text`` は Shared Kernel の定義を**再エクスポートするだけ**にする。
複製するとコンテキストごとに正規化ルールが分岐する（AGENTS.md「空文字の正規化」）。
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from app.application.dispensing.exceptions import DispensingNotFoundError
from app.application.dispensing.inputs import (
    DispensedMedicineInput,
    DispensedRpInput,
    QuantityAdjustmentInput,
    SubstitutionInput,
)
from app.base.application.support import to_optional_text
from app.base.domain.dosage import (
    DailyFrequency,
    DosageCode,
    DosageCodeType,
    DosageInstruction,
    DosageName,
)
from app.base.domain.exceptions import DomainValidationError
from app.base.domain.medicine import (
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PublicExpenseBurden,
    RpNumber,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensedMedicine,
    DispensedRp,
    DispensingId,
    DispensingProcess,
    DispensingProcessRepository,
    PreparationMethod,
    QuantityAdjustment,
    QuantityAdjustmentReason,
    SubstitutionCategory,
    SubstitutionDetail,
    SubstitutionReason,
)

__all__ = [
    "build_dispensed_rps",
    "load_dispensing_or_raise",
    "parse_enum",
    "required_text",
    "to_optional_text",
]


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_enum[E: StrEnum](enum_type: type[E], raw: str, field_name: str) -> E:
    """入力文字列を指定の列挙へ変換する。"""
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name}が不正です。") from exc


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    """入力文字列を ``Decimal`` へ変換する。``float`` を経由しない。"""
    try:
        return Decimal(raw.strip())
    except (ArithmeticError, ValueError) as exc:
        raise DomainValidationError(f"{field_name}は数値で指定してください。") from exc


def _build_substitution(source: SubstitutionInput) -> SubstitutionDetail:
    """代替調剤の記録を構成する。"""
    code = to_optional_text(source.original_code)
    reason = to_optional_text(source.reason)
    return SubstitutionDetail(
        category=parse_enum(SubstitutionCategory, source.category, "代替調剤種別"),
        original_identifier=MedicineIdentifier(
            code_type=parse_enum(
                MedicineCodeType, source.original_code_type, "変更前の薬品コード種別"
            ),
            code=MedicineCode(code) if code is not None else None,
        ),
        original_name=MedicineName(
            required_text(source.original_name, "変更前の薬品名称")
        ),
        reason=SubstitutionReason(reason) if reason is not None else None,
    )


def _build_quantity_adjustment(source: QuantityAdjustmentInput) -> QuantityAdjustment:
    """減数調剤の記録を構成する。"""
    return QuantityAdjustment(
        prescribed_quantity=DispensingQuantity(source.prescribed_quantity),
        reason=parse_enum(QuantityAdjustmentReason, source.reason, "数量調整の理由"),
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
    code = to_optional_text(source.code)
    return DispensedMedicine(
        line_number=MedicineLineNumber(source.line_number),
        identifier=MedicineIdentifier(
            code_type=parse_enum(MedicineCodeType, source.code_type, "薬品コード種別"),
            code=MedicineCode(code) if code is not None else None,
        ),
        name=MedicineName(required_text(source.name, "薬品名称")),
        amount=DosageAmount(_parse_decimal(source.amount, "分量")),
        unit=MedicineUnit(required_text(source.unit, "単位名")),
        substitution=(
            _build_substitution(source.substitution)
            if source.substitution is not None
            else None
        ),
        preparations=tuple(
            parse_enum(PreparationMethod, item, "調製方法")
            for item in source.preparations
        ),
        public_expense_burden=_build_public_expense_burden(source),
    )


def _build_dosage_instruction(source: DispensedRpInput) -> DosageInstruction:
    """用法を構成する。"""
    code = to_optional_text(source.dosage_code)
    return DosageInstruction(
        code_type=parse_enum(DosageCodeType, source.dosage_code_type, "用法コード種別"),
        name=DosageName(required_text(source.dosage_name, "用法名称")),
        code=DosageCode(code) if code is not None else None,
        daily_frequency=(
            DailyFrequency(source.daily_frequency)
            if source.daily_frequency is not None
            else None
        ),
    )


def _build_rp(source: DispensedRpInput) -> DispensedRp:
    """調剤した剤（Rp）を構成する。"""
    return DispensedRp(
        rp_number=RpNumber(source.rp_number),
        category=parse_enum(DosageFormCategory, source.category, "剤形区分"),
        quantity=DispensingQuantity(source.quantity),
        dosage_instruction=_build_dosage_instruction(source),
        medicines=tuple(_build_medicine(item) for item in source.medicines),
        quantity_adjustment=(
            _build_quantity_adjustment(source.quantity_adjustment)
            if source.quantity_adjustment is not None
            else None
        ),
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
        corporate_id=corporate_id,
        dispensing_id=dispensing_id,
    )
    if process is None:
        raise DispensingNotFoundError()
    return process
