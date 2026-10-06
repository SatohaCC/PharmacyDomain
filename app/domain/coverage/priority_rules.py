"""保険・公費の適用順位列を検証する規則。

公費の適用順位は、資格の組み合わせと適用固定値の双方で検証する。前者は選択時、
後者は保存境界の最終防衛であり、検証点は2つある。

一方で**規則そのもの**が2箇所にあると、片方だけ直る事故が起きる。規則は
Coverageに1つだけ置き、各検証箇所は違反種別を自分の例外型とメッセージへ
対応づける。

この関数は int の列だけを扱い、各Domainコンテキストへ依存しない。
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto


class PriorityViolation(Enum):
    """順位列の違反種別。"""

    #: 指定できる件数の上限を超えている。
    EXCEEDS_MAXIMUM = auto()
    #: 同じ順位が複数回指定されている。
    DUPLICATED = auto()
    #: 第一順位から連続していない（欠番がある）。
    NOT_CONSECUTIVE = auto()


def find_priority_violation(
    priorities: Sequence[int], *, maximum: int
) -> PriorityViolation | None:
    """順位列が第一順位から重複なく連続しているかを検証する。

    電子レセプトの公費欄は第一公費から順に埋める。第一公費が空で第三公費だけを
    持つ組み合わせは提出時に返戻されるため、欠番を違反として扱う。

    Args:
        priorities: 検証する順位の列。並び順は問わない。
        maximum: 指定できる件数の上限。

    Returns:
        違反があればその種別、なければ ``None``。
    """
    if len(priorities) > maximum:
        return PriorityViolation.EXCEEDS_MAXIMUM
    if len(priorities) != len(set(priorities)):
        return PriorityViolation.DUPLICATED
    if sorted(priorities) != list(range(1, len(priorities) + 1)):
        return PriorityViolation.NOT_CONSECUTIVE
    return None
