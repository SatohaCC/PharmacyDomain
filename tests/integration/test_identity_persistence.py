"""実DB上で本人と個人アカウントの永続的な対応を守る。"""

import asyncio
from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import AccountPersonId, AccountStatus, UserAccountId
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNames
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.account_person import (
    PostgresAccountPersonRepository,
)
from app.infrastructure.postgres.repositories.user_account import (
    PostgresUserAccountRepository,
)


def _person() -> AccountPerson:
    return AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )


async def _saved_person(factory: async_sessionmaker[AsyncSession]) -> AccountPerson:
    person = _person()
    async with PostgresUnitOfWork(factory) as work:
        await PostgresAccountPersonRepository(work).save(person)
        await work.commit()
    return person


@pytest.mark.asyncio
async def test_本人と個人アカウントを保存して別トランザクションで復元できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    person = await _saved_person(session_factory)
    account = UserAccount(id=UserAccountId.generate(), person_id=person.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresUserAccountRepository(work).save(account)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        actual = await PostgresUserAccountRepository(work).get(account.id)
        assert actual is not None
        assert actual.person_id == person.id
        assert actual.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_同じ本人へのアカウント同時作成は一方だけ確定する(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    person = await _saved_person(session_factory)
    barrier = asyncio.Barrier(2)

    async def save() -> UserAccountId:
        account = UserAccount(id=UserAccountId.generate(), person_id=person.id)
        async with PostgresUnitOfWork(session_factory) as work:
            await barrier.wait()
            await PostgresUserAccountRepository(work).save(account)
            await work.commit()
        return account.id

    results = await asyncio.wait_for(
        asyncio.gather(save(), save(), return_exceptions=True), timeout=15
    )
    assert sum(isinstance(item, UserAccountId) for item in results) == 1
    assert sum(isinstance(item, IdentityConflictError) for item in results) == 1


@pytest.mark.asyncio
async def test_既存アカウントを別人へ付け替えようとしても元の本人が残る(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _saved_person(session_factory)
    second = await _saved_person(session_factory)
    account = UserAccount(id=UserAccountId.generate(), person_id=first.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresUserAccountRepository(work).save(account)
        await work.commit()

    with pytest.raises(IdentityConflictError):
        async with PostgresUnitOfWork(session_factory) as work:
            repository = PostgresUserAccountRepository(work)
            original = await repository.get(account.id)
            assert original is not None
            await repository.save(replace(original, person_id=second.id))
            await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        actual = await PostgresUserAccountRepository(work).get(account.id)
        assert actual is not None
        assert actual.person_id == first.id


@pytest.mark.asyncio
async def test_古い世代のアカウント保存は同時更新エラーになる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    person = await _saved_person(session_factory)
    account = UserAccount(id=UserAccountId.generate(), person_id=person.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresUserAccountRepository(work).save(account)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as old_work:
        old_repository = PostgresUserAccountRepository(old_work)
        old = await old_repository.get(account.id)
        assert old is not None
        async with PostgresUnitOfWork(session_factory) as new_work:
            new_repository = PostgresUserAccountRepository(new_work)
            current = await new_repository.get(account.id)
            assert current is not None
            await new_repository.save(replace(current, status=AccountStatus.SUSPENDED))
            await new_work.commit()
        with pytest.raises(ConcurrentModificationError):
            await old_repository.save(old)
