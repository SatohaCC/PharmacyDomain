"""実行環境のUTC時刻を供給する技術アダプタ。"""

from datetime import UTC, datetime


class SystemUtcClock:
    """システム時計からaware UTC datetimeを返す。"""

    def now(self) -> datetime:
        """現在のUTC時刻を返す。"""
        return datetime.now(UTC)
