"""医薬品マスタに関わるドメインサービス。

無状態（Stateless）であり、本物の集約を引数で受け取る。
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.medicine_catalog.exceptions import (
    MedicineEffectivePeriodConflictError,
)
from app.domain.medicine_catalog.medicine import Medicine


class MedicineEffectivePeriodConflictService:
    """同一薬品コードの収載期間が重ならないことを検証する。"""

    def ensure_no_conflict(
        self,
        medicine: Medicine,
        existing_medicines: Iterable[Medicine],
    ) -> None:
        """収載期間の重複を検証する。

        判定対象は**同じ薬品コードの行どうし**だけ。別の薬品の期間が重なるのは
        当然なので対象にしない。同じ集約IDの現在行は候補から除外し、
        自身の訂正を妨げない。
        """
        for existing in existing_medicines:
            if existing.id == medicine.id:
                continue
            if existing.identifier != medicine.identifier:
                continue
            if existing.effective_period.overlaps(medicine.effective_period):
                code = medicine.identifier.code
                raise MedicineEffectivePeriodConflictError(
                    medicine_code=code.value if code is not None else None
                )
