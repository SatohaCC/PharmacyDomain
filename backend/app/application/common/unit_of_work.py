"""Applicationのunit_of_workを定義する。"""

from __future__ import annotations

from typing import Protocol


class UnitOfWork(Protocol):
    """複数集約を書き込むユースケースが要求する実行中の境界。"""

    def ensure_active(self) -> None:
        """トランザクションが開始済みであることを検証する。"""
        ...
