"""Applicationのbusiness_hoursを定義する。"""

from __future__ import annotations

from app.application.common.input_normalization import to_optional_text
from app.application.store.commands.models import (
    BusinessHourSlotInput,
    ChangeStoreBusinessHoursCommand,
)
from app.domain.store.primitives import BusinessHoursNote
from app.domain.store.value_objects import (
    BusinessDayException,
    BusinessHours,
    BusinessHourSlot,
    WeekdayBusinessHours,
)


def _build_slots(
    inputs: tuple[BusinessHourSlotInput, ...],
) -> tuple[BusinessHourSlot, ...]:
    """入力の時間帯をドメインの値へ移す。"""
    return tuple(
        BusinessHourSlot(opens_at=item.opens_at, closes_at=item.closes_at)
        for item in inputs
    )


def _build_note(raw: str | None) -> BusinessHoursNote | None:
    """空文字を項目解除として扱ってから理由を組み立てる。"""
    normalized = to_optional_text(raw)
    return BusinessHoursNote(normalized) if normalized is not None else None


def _build_hours(command: ChangeStoreBusinessHoursCommand) -> BusinessHours:
    """入力から開局時間の値オブジェクトを組み立てる。"""
    return BusinessHours(
        weekly=tuple(
            WeekdayBusinessHours(weekday=item.weekday, slots=_build_slots(item.slots))
            for item in command.weekly
        ),
        exceptions=tuple(
            BusinessDayException(
                on=item.on, slots=_build_slots(item.slots), note=_build_note(item.note)
            )
            for item in command.exceptions
        ),
    )
