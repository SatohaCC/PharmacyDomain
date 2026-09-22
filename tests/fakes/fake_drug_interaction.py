"""テスト用のブラックボックス相互作用（飲み合わせ）データソースフェイク。"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.prescription.interaction_audit import (
    DrugInteractionDataSource,
    DrugInteractionPair,
)
from app.domain.shared.medicine import YjCode


class FakeDrugInteractionDataSource(DrugInteractionDataSource):
    """インメモリで相互作用データを保持するフェイク。"""

    def __init__(
        self,
        interactions: Mapping[tuple[YjCode, YjCode], DrugInteractionPair] | None = None,
    ) -> None:
        self._interactions: dict[tuple[YjCode, YjCode], DrugInteractionPair] = dict(
            interactions or {}
        )

    def register_interaction(self, pair: DrugInteractionPair) -> None:
        """テスト用に相互作用データを登録する。"""
        normalized_key = (
            min(pair.medicine_a, pair.medicine_b),
            max(pair.medicine_a, pair.medicine_b),
        )
        self._interactions[normalized_key] = pair

    async def find_interactions(
        self, yj_codes: frozenset[YjCode]
    ) -> Mapping[tuple[YjCode, YjCode], DrugInteractionPair]:
        """指定されたYJコード群に含まれる組み合わせの既知の相互作用を返す。"""
        result: dict[tuple[YjCode, YjCode], DrugInteractionPair] = {}
        for (med_a, med_b), pair in self._interactions.items():
            if med_a in yj_codes and med_b in yj_codes:
                result[(med_a, med_b)] = pair
        return result
