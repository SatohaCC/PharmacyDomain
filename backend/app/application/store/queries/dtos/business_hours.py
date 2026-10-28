"""Applicationのbusiness_hoursを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from app.domain.store.value_objects import BusinessHours, BusinessHourSlot


@dataclass(frozen=True, kw_only=True)
class BusinessHourSlotDto:
    """開局時間帯の公開値。"""

    opens_at: time
    closes_at: time

    @classmethod
    def from_slot(cls, slot: BusinessHourSlot) -> BusinessHourSlotDto:
        """時間帯を公開値へ変換する。"""
        return cls(opens_at=slot.opens_at, closes_at=slot.closes_at)


@dataclass(frozen=True, kw_only=True)
class WeekdayBusinessHoursDto:
    """曜日1つ分の公開値。"""

    weekday: str
    slots: tuple[BusinessHourSlotDto, ...]


@dataclass(frozen=True, kw_only=True)
class BusinessDayExceptionDto:
    """特例日の公開値。"""

    on: date
    slots: tuple[BusinessHourSlotDto, ...]
    note: str | None


@dataclass(frozen=True, kw_only=True)
class BusinessHoursDto:
    """開局時間の公開値。"""

    weekly: tuple[WeekdayBusinessHoursDto, ...]
    exceptions: tuple[BusinessDayExceptionDto, ...]

    @classmethod
    def from_value(cls, hours: BusinessHours) -> BusinessHoursDto:
        """開局時間を公開値へ変換する。"""
        return cls(
            weekly=tuple(
                WeekdayBusinessHoursDto(
                    weekday=item.weekday.value,
                    slots=tuple(
                        BusinessHourSlotDto.from_slot(slot) for slot in item.slots
                    ),
                )
                for item in hours.weekly
            ),
            exceptions=tuple(
                BusinessDayExceptionDto(
                    on=item.on,
                    slots=tuple(
                        BusinessHourSlotDto.from_slot(slot) for slot in item.slots
                    ),
                    note=item.note.value if item.note else None,
                )
                for item in hours.exceptions
            ),
        )


@dataclass(frozen=True, kw_only=True)
class StoreOpeningStatusDto:
    """ある日時の開局状況。

    判定に使った業務日と時刻を必ず返す。呼び出し側が自分の時計で「今」を作り
    直すと、タイムゾーンの違いでずれた時刻の答えを受け取ったことに気づけない。
    """

    store_id: str
    state: str
    on: date
    at: time
    slots: tuple[BusinessHourSlotDto, ...]
