"""薬学的処方鑑査における医薬品相互作用（飲み合わせ）のドメインモデルおよびサービス。"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.domain.foundation.value_object import ValueObject
from app.domain.shared.medicine import YjCode


class InteractionSeverity(StrEnum):
    """相互作用の重大度・区分。"""

    CONTRAINDICATED = "contraindicated"
    PRECAUTION = "precaution"
    NONE = "none"

    @property
    def label(self) -> str:
        """日本語表示ラベル。"""
        labels = {
            self.CONTRAINDICATED: "併用禁忌",
            self.PRECAUTION: "併用注意",
            self.NONE: "相互作用なし",
        }
        return labels[self]


@dataclass(frozen=True, kw_only=True)
class DrugInteractionPair(ValueObject):
    """2剤間の相互作用（飲み合わせ）判定結果。"""

    medicine_a: YjCode
    medicine_b: YjCode
    severity: InteractionSeverity
    clinical_condition: str = ""
    mechanism: str = ""
    recommendation: str = ""


@dataclass(frozen=True, kw_only=True)
class DrugInteractionAuditResult(ValueObject):
    """複数医薬品に対する相互作用鑑査結果の全体集約。"""

    target_yj_codes: tuple[YjCode, ...]
    pairs: tuple[DrugInteractionPair, ...]

    @property
    def total_combinations(self) -> int:
        """生成された組み合わせ（ペア）の総数。"""
        return len(self.pairs)

    @property
    def contraindicated_count(self) -> int:
        """併用禁忌ペアの件数。"""
        return sum(
            1 for p in self.pairs if p.severity == InteractionSeverity.CONTRAINDICATED
        )

    @property
    def precaution_count(self) -> int:
        """併用注意ペアの件数。"""
        return sum(
            1 for p in self.pairs if p.severity == InteractionSeverity.PRECAUTION
        )

    @property
    def has_contraindications(self) -> bool:
        """併用禁忌ペアが存在するか。"""
        return self.contraindicated_count > 0

    @property
    def has_precautions(self) -> bool:
        """併用注意ペアが存在するか。"""
        return self.precaution_count > 0

    def contraindicated_pairs(self) -> tuple[DrugInteractionPair, ...]:
        """併用禁忌のペア一覧を返す。"""
        return tuple(
            p for p in self.pairs if p.severity == InteractionSeverity.CONTRAINDICATED
        )

    def precaution_pairs(self) -> tuple[DrugInteractionPair, ...]:
        """併用注意のペア一覧を返す。"""
        return tuple(
            p for p in self.pairs if p.severity == InteractionSeverity.PRECAUTION
        )


class DrugInteractionDataSource(Protocol):
    """ブラックボックス相互作用（飲み合わせ）データベースの抽象プロトコル。"""

    async def find_interactions(
        self, yj_codes: frozenset[YjCode]
    ) -> Mapping[tuple[YjCode, YjCode], DrugInteractionPair]:
        """指定されたYJコード群に含まれる組み合わせの既知の相互作用を検索する。"""
        ...


class DrugInteractionAuditService:
    """複数YJコードの全組み合わせ飲み合わせを判定・構築する無状態ドメインサービス。"""

    async def audit(
        self,
        yj_codes: Sequence[YjCode],
        data_source: DrugInteractionDataSource,
    ) -> DrugInteractionAuditResult:
        """すべての組み合わせの相互作用を判定した鑑査結果を返す。"""
        # 1. 重複コードの一意化（順序を保持）
        unique_codes = tuple(dict.fromkeys(yj_codes))

        # 2. 単剤または0剤の場合は組み合わせなし
        if len(unique_codes) < 2:
            return DrugInteractionAuditResult(
                target_yj_codes=unique_codes,
                pairs=(),
            )

        # 3. 既知の相互作用データを一括取得
        known_interactions = await data_source.find_interactions(
            frozenset(unique_codes)
        )

        # 4. 全ペアの網羅生成と照合（対称性正規化 medicine_a <= medicine_b）
        evaluated_pairs: list[DrugInteractionPair] = []
        for code_x, code_y in itertools.combinations(unique_codes, 2):
            med_a, med_b = (
                (code_x, code_y) if code_x.value <= code_y.value else (code_y, code_x)
            )
            key = (med_a, med_b)
            rev_key = (med_b, med_a)

            found = known_interactions.get(key) or known_interactions.get(rev_key)
            if found is not None:
                # 辞書順で medicine_a <= medicine_b を保証
                if found.medicine_a.value > found.medicine_b.value:
                    pair = dataclasses.replace(
                        found,
                        medicine_a=found.medicine_b,
                        medicine_b=found.medicine_a,
                    )
                else:
                    pair = found
            else:
                pair = DrugInteractionPair(
                    medicine_a=med_a,
                    medicine_b=med_b,
                    severity=InteractionSeverity.NONE,
                    clinical_condition="",
                    mechanism="",
                    recommendation="",
                )
            evaluated_pairs.append(pair)

        # 5. 出力ペアを辞書順で安定ソート
        evaluated_pairs.sort(key=lambda p: (p.medicine_a.value, p.medicine_b.value))

        return DrugInteractionAuditResult(
            target_yj_codes=unique_codes,
            pairs=tuple(evaluated_pairs),
        )
