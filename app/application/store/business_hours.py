"""開局時間の登録と、ある日時に開いているかの照会。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.clock import BUSINESS_TIMEZONE, Clock, business_now
from app.application.common.input_normalization import to_optional_text
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.business_hours import (
    BusinessDayException,
    BusinessHours,
    BusinessHourSlot,
    BusinessHoursNote,
    BusinessWeekday,
    WeekdayBusinessHours,
)
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository
from app.domain.store.store import Store

# --------------------------------------------------------------------------
# 入力（HTTP境界からそのまま受ける）
# --------------------------------------------------------------------------


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


@dataclass(frozen=True, kw_only=True)
class StoreOpeningStatusQuery:
    """開局状況の照会。at を省くと注入した時計の現在時刻で判定する。"""

    corporate_id: str
    store_id: str
    at: datetime | None = None


# --------------------------------------------------------------------------
# 出力（応答モデルとして使うので素の型だけを持つ）
# --------------------------------------------------------------------------


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
    #: その日に適用される開局時間帯。未登録のときは空。
    slots: tuple[BusinessHourSlotDto, ...]


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
                on=item.on,
                slots=_build_slots(item.slots),
                note=_build_note(item.note),
            )
            for item in command.exceptions
        ),
    )


def _business_moment(at: datetime | None, clock: Clock) -> datetime:
    """判定に使う日時を、業務のタイムゾーンへ揃える。

    タイムゾーンの無い日時は受け取らない。UTCのつもりの値とJSTのつもりの値が
    同じ形で届き、9時間ずれた答えを黙って返すことになる。
    """
    if at is None:
        return business_now(clock)
    if at.utcoffset() is None:
        raise DomainValidationError("判定する日時にはタイムゾーンが必要です。")
    return at.astimezone(BUSINESS_TIMEZONE)


def _status_of(store: Store, moment: datetime) -> StoreOpeningStatusDto:
    """判定した日時と、その日の開局時間帯を添えて状態を返す。"""
    on = moment.date()
    at = moment.time()
    hours = store.business_hours
    return StoreOpeningStatusDto(
        store_id=str(store.id.value),
        state=store.opening_state_at(on=on, at=at).value,
        on=on,
        at=at,
        slots=tuple(
            BusinessHourSlotDto.from_slot(slot)
            for slot in (hours.slots_on(on) if hours is not None else ())
        ),
    )


class ChangeStoreBusinessHoursUseCase:
    """開局時間をまとめて置き換える。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: ChangeStoreBusinessHoursCommand
    ) -> BusinessHoursDto:
        """週次の予定と特例日を置き換える。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=StoreId.parse(command.store_id),
        )
        hours = _build_hours(command)
        await self._repository.save(store.change_business_hours(hours))
        return BusinessHoursDto.from_value(hours)


class GetStoreOpeningStatusUseCase:
    """指定日時に店舗が開いているかを返す。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, query: StoreOpeningStatusQuery) -> StoreOpeningStatusDto:
        """業務のタイムゾーンへ揃えてから判定する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_STORE
        )
        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=StoreId.parse(query.store_id),
        )
        return _status_of(store, _business_moment(query.at, self._clock))


__all__ = [
    "BusinessDayExceptionDto",
    "BusinessDayExceptionInput",
    "BusinessHourSlotDto",
    "BusinessHourSlotInput",
    "BusinessHoursDto",
    "ChangeStoreBusinessHoursCommand",
    "ChangeStoreBusinessHoursUseCase",
    "GetStoreOpeningStatusUseCase",
    "StoreOpeningStatusDto",
    "StoreOpeningStatusQuery",
    "WeekdayBusinessHoursDto",
    "WeekdayBusinessHoursInput",
]
