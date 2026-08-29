"""処方と調剤が共有する薬品単位の公費負担区分（Shared Kernel）。"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import ClassVar

from app.domain.foundation.value_object import ValueObject


@dataclass(frozen=True, kw_only=True)
class PublicExpenseBurden(ValueObject):
    """薬品単位の公費負担区分。

    出典: JAHIS Ver.1.11 レコードNo.231 負担区分レコード
    （処方箋内出力／未出力混在不可、全薬品出力 or 全薬品未出力、1薬品に1レコード）。

    処方箋の公費枠は第一/第二/第三/**特殊**であり、電子レセプトの第一〜第四とは
    別軸である。特殊公費の負担者番号は ``N20``（漢字半角混在可・数字以外可）で
    ``ClaimPublicPayerNumber``（8桁）の不変条件を満たせないため、Claim へは
    写さない。
    """

    first: bool = False
    second: bool = False
    third: bool = False
    special: bool = False

    _FIELD_LABELS: ClassVar[dict[str, str]] = {
        "first": "第一公費負担区分",
        "second": "第二公費負担区分",
        "third": "第三公費負担区分",
        "special": "特殊公費負担区分",
    }

    @property
    def bears_any(self) -> bool:
        """いずれかの公費が負担するか。"""
        return self.first or self.second or self.third or self.special

    #: 公費枠の並び。判定を枠ごとの ``if`` で書くと枠の追加時に必ず書き漏れる。
    _SLOTS: ClassVar[tuple[str, ...]] = ("first", "second", "third", "special")

    def uncovered_slots_against(
        self, available: PublicExpenseBurden
    ) -> tuple[str, ...]:
        """自分が負担ありとした枠のうち、``available`` に無い枠の名称を返す。

        「負担しない」とした枠は裏付けが無くても構わないので対象にしない。
        戻り値は表示用の日本語名称であり、空タプルなら裏付けが揃っている。
        """
        return tuple(
            self._FIELD_LABELS[slot]
            for slot in self._SLOTS
            if getattr(self, slot) and not getattr(available, slot)
        )


def _verify_public_expense_slots_are_complete() -> None:
    """公費枠の並びが実フィールドを網羅していることを検証する。

    枠を1つ足して ``_SLOTS`` への追記を忘れると、その枠だけ裏付けの検証を
    素通りする。読み込み時に落とすための不変条件チェックであり、
    最適化実行（``python -O``）でも省略されないよう ``assert`` は使わない。
    """
    declared = frozenset(PublicExpenseBurden._SLOTS)
    actual = frozenset(item.name for item in fields(PublicExpenseBurden))
    if declared != actual:
        raise RuntimeError(
            "PublicExpenseBurden の公費枠一覧がフィールド定義と一致していません。"
        )


_verify_public_expense_slots_are_complete()
