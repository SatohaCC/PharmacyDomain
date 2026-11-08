"""日本の業務日を扱う共通時間関数。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Final

JAPAN_TIMEZONE: Final = timezone(timedelta(hours=9))


def japan_business_date(value: datetime) -> date:
    """aware datetimeを日本時間の暦日へ変換する。"""
    return value.astimezone(JAPAN_TIMEZONE).date()
