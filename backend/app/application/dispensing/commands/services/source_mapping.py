"""処方元の用量を、利用する調剤側の不変値へ明示変換する。"""

from __future__ import annotations

from app.domain.dispensing.primitives import (
    DailyFrequency,
    DosageCode,
    DosageCodeType,
    DosageName,
)
from app.domain.dispensing.value_objects import DosageInstruction
from app.domain.prescription.value_objects import (
    DosageInstruction as SourceDosageInstruction,
)


def dispensing_dosage(value: SourceDosageInstruction) -> DosageInstruction:
    """処方記載の用法を調剤時点の用法へ固定する。"""
    return DosageInstruction(
        code_type=DosageCodeType(value.code_type.value),
        name=DosageName(value.name.value),
        code=DosageCode(value.code.value) if value.code is not None else None,
        daily_frequency=DailyFrequency(value.daily_frequency.value)
        if value.daily_frequency is not None
        else None,
    )
