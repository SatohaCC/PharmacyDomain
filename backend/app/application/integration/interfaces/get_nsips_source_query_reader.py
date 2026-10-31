"""Integration NSIPS 原本読取 Reader Protocol。"""

from __future__ import annotations

from typing import Protocol

from app.application.integration.queries.dtos.get_nsips_source import NsipsSourceDto
from app.application.integration.queries.models import GetNsipsSourceQuery


class GetNsipsSourceQueryReader(Protocol):
    """NSIPS原本データを参照用DTOとして取得するReader境界。"""

    async def read(self, query: GetNsipsSourceQuery) -> NsipsSourceDto:
        """指定された受付IDの原本データを返す。"""
        ...
