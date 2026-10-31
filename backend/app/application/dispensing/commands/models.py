"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, kw_only=True)
class SubstitutionInput:
    """軸1: 代替調剤の入力。処方薬品そのものを置き換えたときだけ指定する。"""

    category: str
    original_code_type: str
    original_name: str
    original_code: str | None = None
    reason: str | None = None
    inquiry_number: int | None = None


@dataclass(frozen=True, kw_only=True)
class QuantityAdjustmentInput:
    """軸2: 減数調剤の入力。処方時の数量を併せて受け取る。"""

    prescribed_quantity: int
    reason: str
    inquiry_number: int | None = None


@dataclass(frozen=True, kw_only=True)
class DispensedMedicineInput:
    """調剤した薬品1明細の入力。"""

    line_number: int
    code_type: str
    name: str
    amount: str
    unit: str
    code: str | None = None
    substitution: SubstitutionInput | None = None
    preparations: tuple[str, ...] = field(default_factory=tuple)
    public_expense_first: bool = False
    public_expense_second: bool = False
    public_expense_third: bool = False
    public_expense_special: bool = False


@dataclass(frozen=True, kw_only=True)
class DispensedRpInput:
    """調剤した剤（Rp）の入力。"""

    rp_number: int
    category: str
    quantity: int
    dosage_code_type: str
    dosage_name: str
    medicines: tuple[DispensedMedicineInput, ...]
    dosage_code: str | None = None
    daily_frequency: int | None = None
    quantity_adjustment: QuantityAdjustmentInput | None = None


@dataclass(frozen=True, kw_only=True)
class StartDispensingCommand:
    """調剤セッション開始の入力データ。開始日時は含めない。"""

    corporate_id: str
    store_id: str
    prescription_id: str
    iteration: int
    dispensed_date: date | None
    dispensed_rps: tuple[DispensedRpInput, ...]
    dispenser_id: str | None = None
    split_reason: str | None = None
    total_split_count: int | None = None
