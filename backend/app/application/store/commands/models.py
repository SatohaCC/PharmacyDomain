"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum

from app.domain.store.primitives import BusinessWeekday


@dataclass(frozen=True, kw_only=True)
class BusinessHourSlotInput:
    """開局時間帯1件。終了時刻の 00:00 はその日の24時を指す。"""

    opens_at: time
    closes_at: time


@dataclass(frozen=True, kw_only=True)
class WeekdayBusinessHoursInput:
    """曜日1つ分の開局予定。時間帯が空なら定休日。"""

    weekday: BusinessWeekday
    slots: tuple[BusinessHourSlotInput, ...] = ()


@dataclass(frozen=True, kw_only=True)
class BusinessDayExceptionInput:
    """日付を指定した上書き。時間帯が空なら臨時休業。"""

    on: date
    slots: tuple[BusinessHourSlotInput, ...] = ()
    note: str | None = None


@dataclass(frozen=True, kw_only=True)
class ChangeStoreBusinessHoursCommand:
    """開局時間をまとめて置き換える入力。"""

    corporate_id: str
    store_id: str
    weekly: tuple[WeekdayBusinessHoursInput, ...]
    exceptions: tuple[BusinessDayExceptionInput, ...] = ()


class ManagerAction(StrEnum):
    """任命履歴への更新分類。"""

    APPOINT = "appoint"
    REPLACE = "replace"
    CANCEL = "cancel"
    END = "end"
