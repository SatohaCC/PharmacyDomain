"""現在時刻を外側から供給するためのApplication境界。"""

from datetime import date, datetime
from typing import Final, Protocol
from zoneinfo import ZoneInfo

#: 業務日を決めるタイムゾーン。
#:
#: 調剤も受付も日本国内の営業日で数えるため、UTCの日付では日をまたぐ前後で
#: 別の業務日になる。各所で ``ZoneInfo("Asia/Tokyo")`` と書くと、片方だけを
#: 直したときに「同じ今日」が経路ごとにずれる。
BUSINESS_TIMEZONE: Final = ZoneInfo("Asia/Tokyo")


class Clock(Protocol):
    """タイムゾーン付き現在時刻を返す時計。"""

    def now(self) -> datetime:
        """現在のaware datetimeを返す。"""
        ...


def business_now(clock: Clock) -> datetime:
    """注入した時計を業務のタイムゾーンへ変換する。

    業務日だけでなく、開局時間の判定も同じ時間帯で数える必要がある。変換を
    2箇所に書くと、日付と時刻が別のタイムゾーンで決まる状態を作れてしまう。
    """
    return clock.now().astimezone(BUSINESS_TIMEZONE)


def business_date(clock: Clock) -> date:
    """注入した時計から業務日を決める。

    ``date.today()`` を使わないのは、時計を注入した意味が消えるからである
    （``DTZ011`` が lint で落とす）。変換を1箇所に置くことで、業務日の定義を
    後から変えるときに直す場所が1つで済む。
    """
    return business_now(clock).date()


__all__ = ["BUSINESS_TIMEZONE", "Clock", "business_date", "business_now"]
