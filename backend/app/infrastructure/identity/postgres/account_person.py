"""本人情報のPostgreSQL保存契約。"""

from sqlalchemy import select

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import AccountPerson
from app.domain.identity.repositories import AccountPersonRepository
from app.domain.shared.actor import AccountPersonId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import account_people

ACCOUNT_PERSON_MAPPING = AggregateMapping(
    table=account_people,
    aggregate_type=AccountPerson,
    label="本人",
    search_columns=lambda person: {
        "id": person.id.value,
        "corporate_id": person.corporate_id.value,
    },
)


class PostgresAccountPersonRepository(PostgresRepositoryBase, AccountPersonRepository):
    """本人IDで人物を保存・取得する。"""

    async def get(self, person_id: AccountPersonId) -> AccountPerson | None:
        """本人情報を取得する。"""
        return await self.get_by_id(ACCOUNT_PERSON_MAPPING, person_id)

    async def find_for_corporate(
        self, corporate_id: CorporateId, person_id: AccountPersonId
    ) -> AccountPerson | None:
        """法人スコープ内で本人情報を取得する。"""
        return await self.find_one(
            ACCOUNT_PERSON_MAPPING,
            select(account_people).where(
                account_people.c.id == person_id.value,
                account_people.c.corporate_id == corporate_id.value,
            ),
        )

    async def save(self, person: AccountPerson) -> None:
        """本人情報を保存する。"""
        await self.save_aggregate(ACCOUNT_PERSON_MAPPING, person)
