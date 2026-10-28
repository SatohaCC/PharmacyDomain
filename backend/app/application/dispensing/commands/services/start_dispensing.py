"""Applicationのstart_dispensingを定義する。"""

from __future__ import annotations

from app.domain.dispensing.entities import DispensingProcess


def _find_previous(
    existing: list[DispensingProcess], iteration: int
) -> DispensingProcess | None:
    """直前の回のセッションを探す。

    他薬局で実施された回は自局のRepositoryに無いため ``None`` になりうる。
    そのときに検証を飛ばすか拒否するかは Domain Service 側の判断
    （``PreviousDispensingUnknownError`` として拒否する）。
    """
    for item in existing:
        if item.iteration.value == iteration - 1:
            return item
    return None
