"""Applicationのlist_storesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.store.entities import Store


@dataclass(frozen=True, kw_only=True)
class StoreSummaryDto:
    """店舗一覧の出力データ（DTO）。"""

    id: str
    corporate_id: str
    name: str
    name_kana: str
    code: str | None

    @classmethod
    def from_entity(cls, store: Store) -> StoreSummaryDto:
        return cls(
            id=str(store.id.value),
            corporate_id=str(store.corporate_id.value),
            name=store.names.name.value,
            name_kana=store.names.kana.value,
            code=store.code.value if store.code else None,
        )
