"""`Clock` のテスト用実装。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.base.application.clock import Clock

#: 固定の既定時刻（aware UTC）。テストが日付を指定しないときに使う。
DEFAULT_NOW = datetime(2026, 8, 23, 3, 0, tzinfo=UTC)


class FakeClock(Clock):
    """常に同じ時刻を返し、必要なら明示的に進められる時計。"""

    def __init__(self, now: datetime = DEFAULT_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        """固定された aware UTC 時刻を返す。"""
        return self._now

    def advance(self, delta: timedelta) -> None:
        """時刻を進める。経過を伴うシナリオのテストで使う。"""
        self._now += delta
