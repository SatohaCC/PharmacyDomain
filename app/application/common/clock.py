"""現在時刻を外側から供給するためのApplication境界。"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """タイムゾーン付き現在時刻を返す時計。"""

    def now(self) -> datetime:
        """現在のaware datetimeを返す。"""
        ...
