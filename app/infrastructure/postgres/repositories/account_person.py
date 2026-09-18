"""本人情報のPostgreSQL保存契約。"""

from app.domain.identity.account_person import AccountPerson
from app.domain.identity.primitives import AccountPersonId
from app.domain.identity.repository import AccountPersonRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import account_people

ACCOUNT_PERSON_MAPPING = AggregateMapping(
    table=account_people,
    aggregate_type=AccountPerson,
    label="本人",
    search_columns=lambda person: {"id": person.id.value},
)


class PostgresAccountPersonRepository(PostgresRepositoryBase, AccountPersonRepository):
    """本人IDで人物を保存・取得する。"""

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        """本人情報を取得する。"""
        return await self.get_by_id(ACCOUNT_PERSON_MAPPING, person_id)

    async def save(self, person: AccountPerson) -> None:
        """本人情報を保存する。"""
        await self.save_aggregate(ACCOUNT_PERSON_MAPPING, person)
