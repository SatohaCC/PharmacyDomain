"""Applicationのget_medicineを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.medicine_catalog.entities import Medicine


@dataclass(frozen=True, kw_only=True)
class MedicineDto:
    """医薬品マスタ1行の出力DTO。

    導出値（``is_narcotic`` 等）も返す。呼び出し側が生の事実から判定し直すと、
    規則の実装が2箇所に分かれる。
    """

    id: str
    code_type: str
    code: str
    name: str
    unit: str
    dosage_form: str
    listed_on: str
    withdrawn_on: str | None
    catalog_version: str
    narcotic_category: str
    generic_category: str
    has_dosage_limit: bool
    is_analgesic_antiinflammatory: bool
    is_dermatological: bool
    is_narcotic: bool
    is_refill_restricted_patch: bool
    forbids_refill: bool

    @classmethod
    def from_entity(cls, medicine: Medicine) -> MedicineDto:
        """マスタ行からDTOを生成する。"""
        code = medicine.identifier.code
        withdrawn_on = medicine.effective_period.withdrawn_on
        return cls(
            id=str(medicine.id.value),
            code_type=medicine.identifier.code_type.value,
            code=code.value if code is not None else "",
            name=medicine.name.value,
            unit=medicine.unit.value,
            dosage_form=medicine.dosage_form.value,
            listed_on=medicine.effective_period.listed_on.value.isoformat(),
            withdrawn_on=withdrawn_on.value.isoformat()
            if withdrawn_on is not None
            else None,
            catalog_version=medicine.catalog_version.value.isoformat(),
            narcotic_category=medicine.narcotic_category.value,
            generic_category=medicine.generic_category.value,
            has_dosage_limit=medicine.has_dosage_limit,
            is_analgesic_antiinflammatory=medicine.is_analgesic_antiinflammatory,
            is_dermatological=medicine.is_dermatological,
            is_narcotic=medicine.is_narcotic,
            is_refill_restricted_patch=medicine.is_refill_restricted_patch,
            forbids_refill=medicine.forbids_refill,
        )
