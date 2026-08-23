"""受付で選択した資格を、元資格IDと請求固定値を枠ごとに束ねて表す値。

以前は「正規化済みの元資格ID列」と「請求用 ``CoverageSnapshot``」を並列の2つの
フィールドとして持ち、両者は「医療保険 → 公費順位順」という**並び順の規約**で
対応させていた。件数一致しか検証できず、順序が入れ替わった履歴も構築できた。

対応を型で表せなかったのは、``CoverageSnapshot`` が元IDを一切持たず
``SourceCoverageId`` も素の UUID で、集約内に照合材料が存在しなかったためである。
そこで検証を足すのではなく型の形を変える。枠（医療保険枠・公費枠）がIDと値を
分離不能に1対1で束ねるので、「医療保険IDが先頭でない」「公費IDが順位とズレる」
という状態がそもそも表現できなくなり、件数一致の検証自体が不要になる。

なお「その元IDが本当にその資格を指すか」はここでは守れない。台帳を引かないと
判定できず、それは ``CoverageValidityBoundary`` の再検証の仕事である。
集約内で機械化できる上限は枠構造の一致までである。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.base.domain.value_object import ValueObject
from app.domain.claim.coverage_snapshot import (
    CoverageSnapshot,
    InsuranceCoverageSnapshot,
    PublicExpenseCoverageSnapshot,
)
from app.domain.claim.primitives import ClaimCoveragePriority
from app.domain.reception.exceptions import CoverageSelectionInvalidError
from app.domain.reception.primitives import SourceCoverageId


@dataclass(frozen=True, kw_only=True)
class SelectedInsuranceSource(ValueObject):
    """医療保険枠。選択元の患者資格IDと請求時点の固定値を1対1で束ねる。"""

    source_coverage_id: SourceCoverageId
    values: InsuranceCoverageSnapshot

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "values": "医療保険スナップショット",
    }


@dataclass(frozen=True, kw_only=True)
class SelectedPublicExpenseSource(ValueObject):
    """公費枠1つ。適用順位は値側が持つので、IDと順位が離れることがない。"""

    source_coverage_id: SourceCoverageId
    values: PublicExpenseCoverageSnapshot

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "values": "公費スナップショット",
    }

    @property
    def priority(self) -> ClaimCoveragePriority:
        """適用順位を値側から返す。"""
        return self.values.priority


@dataclass(frozen=True, kw_only=True)
class CoverageSelection(ValueObject):
    """医療保険枠0〜1個と公費枠0〜4個からなる、受付時の資格選択。"""

    insurance: SelectedInsuranceSource | None = None
    public_expenses: tuple[SelectedPublicExpenseSource, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険枠",
        "public_expenses": "公費枠",
    }

    def _normalize_fields(self) -> None:
        """公費枠を適用順位順へ正規化する。

        順位は値側にあるので、並べ替えてもIDとの対応は動かない。どんな入力順で
        渡しても同一の ``CoverageSelection`` になり、並び順という自由度が消える。
        """
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, SelectedPublicExpenseSource)
            for item in self.public_expenses
        ):
            return
        ordered = tuple(
            sorted(self.public_expenses, key=lambda item: item.priority.value)
        )
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """元資格IDの重複を拒否し、値側の組み合わせ規則も凍結時に走らせる。

        件数一致の検証は不要である。枠の外にIDも値も存在しえないため、
        件数がズレた状態を作る手段が構造的に無い。

        Raises:
            CoverageSelectionInvalidError: 同じ元資格IDを複数の枠へ指定した場合。
            CoverageCombinationInvalidError: 枠が1つも無い、公費が第五以降まで
                ある、公費順位が重複または第一公費から連続していない場合。
                値側の規則なので Claim の例外をそのまま透過させる（Receptionで
                包み直すと同じ規則が2箇所に定義されるため）。
        """
        source_ids = self.source_coverage_ids
        if len(source_ids) != len(set(source_ids)):
            raise CoverageSelectionInvalidError(
                "同じ選択元患者資格IDを複数の枠へ指定できません。"
            )
        # 遅延評価にすると「作れてしまうが後で爆発する」ため、構築時に走らせる。
        self._build_snapshot()

    def _build_snapshot(self) -> CoverageSnapshot:
        """枠から請求用スナップショットを組み立てる。"""
        return CoverageSnapshot(
            insurance=self.insurance.values if self.insurance is not None else None,
            public_expenses=tuple(item.values for item in self.public_expenses),
        )

    @property
    def snapshot(self) -> CoverageSnapshot:
        """請求へ渡す不変スナップショット。枠構造からの導出値。"""
        return self._build_snapshot()

    @property
    def source_coverage_ids(self) -> tuple[SourceCoverageId, ...]:
        """選択元IDを医療保険、公費順位順で返す。枠構造からの導出値。

        崩れた並びを保持する記憶域が存在しないので、毎回この順で生成される。
        """
        insurance = (
            (self.insurance.source_coverage_id,) if self.insurance is not None else ()
        )
        return insurance + tuple(
            item.source_coverage_id for item in self.public_expenses
        )
