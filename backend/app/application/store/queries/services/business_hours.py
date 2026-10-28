"""Applicationのbusiness_hoursを定義する。"""

from __future__ import annotations

from datetime import datetime

from app.application.common.clock import BUSINESS_TIMEZONE, Clock, business_now
from app.application.store.queries.dtos.business_hours import (
    BusinessHourSlotDto,
    StoreOpeningStatusDto,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.entities import Store


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
