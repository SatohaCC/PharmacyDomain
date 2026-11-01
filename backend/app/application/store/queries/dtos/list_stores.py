"""Applicationのlist_storesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.store.entities import Store


@dataclass(frozen=True, kw_only=True)
class StoreSummaryDto:
    """店舗一覧の出力データ（DTO）。"""

    id: str
    corporate_id: str
    name: str
    name_kana: str
    code: str | None
    status: str = "active"
    is_community_linkage: bool = False
    is_specialized_linkage: bool = False
    is_health_support: bool = False

    @classmethod
    def from_entity(cls, store: Store, *, as_of: date | None = None) -> StoreSummaryDto:
        cert = store.certifications
        is_community = False
        is_specialized = False
        is_health = False
        if cert:
            if cert.community_linkage is not None:
                is_community = (
                    cert.community_linkage.is_effective_on(as_of)
                    if as_of is not None
                    else True
                )
            if cert.specialized_linkage is not None:
                is_specialized = (
                    cert.specialized_linkage.is_effective_on(as_of)
                    if as_of is not None
                    else True
                )
            if cert.health_support is not None:
                is_health = (
                    cert.health_support.notified_on <= as_of
                    if as_of is not None
                    else True
                )
        return cls(
            id=str(store.id.value),
            corporate_id=str(store.corporate_id.value),
            name=store.names.name.value,
            name_kana=store.names.kana.value,
            code=store.code.value if store.code else None,
            status=store.status.value,
            is_community_linkage=is_community,
            is_specialized_linkage=is_specialized,
            is_health_support=is_health,
        )
