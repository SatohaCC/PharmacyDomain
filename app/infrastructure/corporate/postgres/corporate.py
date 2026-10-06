"""法人集約の PostgreSQL Repository。

法人名は法人をまたいで一意なので、この集約だけは検索も一意性制約も
``corporate_id`` で絞らない。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.corporate.primitives import CorporateId, CorporateName
from app.domain.corporate.repository import (
    CorporateCatalogRepository,
    CorporateRepository,
)
from app.domain.corporate.search import CorporateSearch, CorporateSearchRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import corporates


def _corporate_columns(corporate: Corporate) -> dict[str, object]:
    """検索・一意性制約に使う列を法人から導く。"""
    return {
        "id": corporate.id.value,
        "name": corporate.name.value,
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
    }


CORPORATE_MAPPING = AggregateMapping(
    table=corporates,
    aggregate_type=Corporate,
    label="法人",
    search_columns=_corporate_columns,
)


class PostgresCorporateRepository(
    PostgresRepositoryBase,
    CorporateRepository,
    CorporateCatalogRepository,
    CorporateSearchRepository,
):
    """法人集約を PostgreSQL へ保存・検索する。"""

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        """IDで法人を検索する。"""
        return await self.get_by_id(CORPORATE_MAPPING, corporate_id)

    async def save(self, corporate: Corporate) -> None:
        """法人を新規登録または更新し、法人名の重複をDBで拒否する。"""
        await self.save_with_conflict_map(
            CORPORATE_MAPPING,
            corporate,
            conflicts={"uq_corporates_name": CorporateNameAlreadyExistsError},
        )

    async def exists_by_name(
        self,
        name: CorporateName,
        *,
        excluding_id: CorporateId | None = None,
    ) -> bool:
        """法人名が既に使われているかを検索する。"""
        statement = select(corporates.c.id).where(corporates.c.name == name.value)
        if excluding_id is not None:
            statement = statement.where(corporates.c.id != excluding_id.value)
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_all(self) -> list[Corporate]:
        """ベンダー用に全法人を名前順で返す。"""
        return await self.find_all(
            CORPORATE_MAPPING,
            select(corporates).order_by(corporates.c.name, corporates.c.id),
        )

    async def search(self, query: CorporateSearch) -> list[Corporate]:
        """名称の特殊文字も文字通りに検索しID順でページを返す。"""
        statement = select(corporates)
        if query.name is not None:
            statement = statement.where(
                corporates.c.name.contains(query.name, autoescape=True)
            )
        if query.status is not None:
            statement = statement.where(corporates.c.status == query.status.value)
        if query.after_id is not None:
            statement = statement.where(corporates.c.id > query.after_id.value)
        return await self.find_all(
            CORPORATE_MAPPING, statement.order_by(corporates.c.id).limit(query.limit)
        )
