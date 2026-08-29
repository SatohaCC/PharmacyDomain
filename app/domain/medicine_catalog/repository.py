"""医薬品マスタのリポジトリインターフェース。

**法人IDを取らない。** 薬価基準は国が定めるものであり、法人ごとに内容が違わない
（``primitives.py`` の冒頭を参照）。既存の全 Repository が `corporate_id` を
取るのに対し、ここだけが例外である。
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.base.domain.medicine import MedicineIdentifier
from app.domain.medicine_catalog.medicine import Medicine
from app.domain.medicine_catalog.primitives import MedicineCatalogEntryId


class MedicineCatalogRepository(Protocol):
    """医薬品マスタを検索・永続化するための操作インターフェース。"""

    async def get(self, entry_id: MedicineCatalogEntryId) -> Medicine | None:
        """マスタ行を識別子で取得する。"""
        ...

    async def find_effective(
        self,
        *,
        identifier: MedicineIdentifier,
        as_of: date,
    ) -> Medicine | None:
        """指定日に有効なマスタ行を返す。

        **適用日を必ず受け取る。** 麻薬指定も経過措置期限も時点で変わるので、
        「今」で引くと過去の調剤を誤判定する。同じ薬品コードで期間が重なる行は
        :meth:`save` の契約により存在しないため、戻り値は一意に定まる。

        マスタに無い薬品は ``None`` を返す。呼び出し側はこれを「該当しない」へ
        倒さず、判定不能として拒否する。
        """
        ...

    async def list_versions(self, identifier: MedicineIdentifier) -> list[Medicine]:
        """同じ薬品コードの全ての行を収載日の昇順で返す。

        改定履歴の確認に使う。件数は版の数であって、薬品の数ではない。
        """
        ...

    async def save(self, medicine: Medicine) -> None:
        """同一薬品コードの収載期間の重複を原子的に拒否して保存する。

        同じ集約IDの現在行を除外した上で、期間が1日でも重なる行があれば
        ``MedicineEffectivePeriodConflictError`` を送出する。重なると、ある日付で
        引いたときに2行が返り「その日のマスタ」が一意に定まらなくなる。

        Applicationの事前readは早期エラー用であり原子性の代替ではない。
        """
        ...
