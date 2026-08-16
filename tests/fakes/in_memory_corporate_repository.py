from __future__ import annotations

import copy

from app.domain.corporate import (
    Corporate,
    CorporateCatalogRepository,
    CorporateId,
    CorporateName,
    CorporateNameAlreadyExistsError,
    CorporateRepository,
)


class InMemoryCorporateRepository(CorporateRepository, CorporateCatalogRepository):
    def __init__(self) -> None:
        self.items: dict[CorporateId, Corporate] = {}
        #: ``save()`` が呼ばれた回数。変更が無いときに保存を省いているかの検証に使う。
        self.save_count = 0

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        item = self.items.get(corporate_id)
        if item is None:
            return None
        return copy.deepcopy(item)

    async def save(self, corporate: Corporate) -> None:
        self.save_count += 1

        if await self.exists_by_name(corporate.name, excluding_id=corporate.id):
            raise CorporateNameAlreadyExistsError(
                f"法人名 '{corporate.name.value}' は既に登録されています。"
            )
        self.items[corporate.id] = copy.deepcopy(corporate)

    async def exists_by_name(
        self,
        name: CorporateName,
        *,
        excluding_id: CorporateId | None = None,
    ) -> bool:
        return any(
            item.name == name and item.id != excluding_id
            for item in self.items.values()
        )

    async def list_all(self) -> list[Corporate]:
        return [copy.deepcopy(item) for item in self.items.values()]
