"""法人ページ検索のインメモリ実装。"""

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.search import CorporateSearch, CorporateSearchRepository


class InMemoryCorporateSearchRepository(CorporateSearchRepository):
    """ページ要求を記録し、条件内の実法人を返す。"""

    def __init__(self, items: list[Corporate]) -> None:
        self.items = items
        self.queries: list[CorporateSearch] = []

    async def search(self, query: CorporateSearch) -> list[Corporate]:
        """ID順に条件と件数制限を適用する。"""
        self.queries.append(query)
        matching = (
            item
            for item in self.items
            if (query.name is None or query.name in item.name.value)
            and (query.status is None or item.status == query.status)
            and (query.after_id is None or item.id.value > query.after_id.value)
        )
        return sorted(matching, key=lambda item: item.id.value)[: query.limit]
