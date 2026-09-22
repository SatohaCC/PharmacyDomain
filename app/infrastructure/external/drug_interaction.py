"""ブラックボックス医薬品相互作用（飲み合わせ）データソース。"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.prescription.interaction_audit import (
    DrugInteractionDataSource,
    DrugInteractionPair,
)
from app.domain.shared.medicine import YjCode


class BlackBoxDrugInteractionDataSource(DrugInteractionDataSource):
    """ブラックボックス相互作用データソースの既定実装（外部DB未接続時は空の相互作用を返す）。"""

    async def find_interactions(
        self, yj_codes: frozenset[YjCode]
    ) -> Mapping[tuple[YjCode, YjCode], DrugInteractionPair]:
        """指定されたYJコード群に含まれる組み合わせの既知の相互作用を検索する。"""
        return {}
