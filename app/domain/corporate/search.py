"""法人管理画面のページ検索契約。"""

from dataclasses import dataclass
from typing import Protocol

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId, CorporateStatus


@dataclass(frozen=True, kw_only=True)
class CorporateSearch:
    """検索条件とID順のページ境界。"""

    name: str | None
    status: CorporateStatus | None
    after_id: CorporateId | None
    limit: int


class CorporateSearchRepository(Protocol):
    """絞り込みと件数制限を永続化側で適用する。"""

    async def search(self, query: CorporateSearch) -> list[Corporate]:
        """ID昇順で指定件数以内の法人を返す。"""
        ...
