"""個人アカウントのPostgreSQL保存契約。"""

from sqlalchemy import select

from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import (
    AccountPersonId,
    ExternalSubjectKey,
    UserAccountId,
)
from app.domain.identity.repository import UserAccountRepository
from app.domain.identity.user_account import UserAccount
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import user_accounts

USER_ACCOUNT_MAPPING = AggregateMapping(
    table=user_accounts,
    aggregate_type=UserAccount,
    label="個人アカウント",
    search_columns=lambda account: {
        "id": account.id.value,
        "person_id": account.person_id.value,
        "status": account.status.value,
        "external_subject": account.external_subject.value
        if account.external_subject is not None
        else None,
    },
)


class PostgresUserAccountRepository(PostgresRepositoryBase, UserAccountRepository):
    """本人対応の一意性と変更不可をDBで守る。"""

    async def get(self, account_id: UserAccountId) -> UserAccount | None:
        """個人アカウントを取得する。"""
        return await self.get_by_id(USER_ACCOUNT_MAPPING, account_id)

    async def get_by_person(self, person_id: AccountPersonId) -> UserAccount | None:
        """本人から個人アカウントを取得する。"""
        return await self.find_one(
            USER_ACCOUNT_MAPPING,
            select(user_accounts).where(user_accounts.c.person_id == person_id.value),
        )

    async def save(self, account: UserAccount) -> None:
        """二重作成と別人への付け替えを拒否して保存する。"""
        await self.save_with_conflict_map(
            USER_ACCOUNT_MAPPING,
            account,
            conflicts={
                "uq_user_accounts_person_id": IdentityConflictError,
                "ck_user_accounts_person_immutable": IdentityConflictError,
                "uq_user_accounts_external_subject": IdentityConflictError,
            },
        )

    async def get_by_subject(self, subject: ExternalSubjectKey) -> UserAccount | None:
        """本人確認基盤で検証済みの主体で検索する。"""
        return await self.find_one(
            USER_ACCOUNT_MAPPING,
            select(user_accounts).where(
                user_accounts.c.external_subject == subject.value
            ),
        )
