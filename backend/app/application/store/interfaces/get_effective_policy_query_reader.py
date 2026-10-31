"""Applicationのget_effective_policy_query_readerを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.store.queries.dtos.get_effective_policy import EffectivePolicyDto
from app.application.store.queries.models import GetEffectivePolicyQuery


class GetEffectivePolicyQueryReader(Protocol):
    """店舗の実効ポリシーを参照用DTOへ射影する契約。"""

    async def read(self, query: GetEffectivePolicyQuery) -> EffectivePolicyDto:
        """店舗の実効ポリシーを取得する。"""
        ...
