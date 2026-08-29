"""調剤内容の入力DTO。

処方箋側と同じく、剤（Rp）→薬品明細の入れ子をそのまま受け取る。平坦にすると
「何番目の要素が何番目の薬品か」が並び順の規約になる。

**用量は ``str`` で受け取る。** ``float`` を経由すると誤差が入り、用量の一致を
前提にした判定が壊れる。``Decimal`` への変換は ``support.py`` だけが行う。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class SubstitutionInput:
    """軸1: 代替調剤の入力。処方薬品そのものを置き換えたときだけ指定する。"""

    category: str
    original_code_type: str
    original_name: str
    original_code: str | None = None
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class QuantityAdjustmentInput:
    """軸2: 減数調剤の入力。処方時の数量を併せて受け取る。"""

    prescribed_quantity: int
    reason: str


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
    #: 軸3: 調製方法。複数同時に成立する（一包化しつつ粉砕する等）。
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
