"""実PostgreSQLを用いた法人スコープの本人・アカウント整合性テスト。

TC-023: 法人帰属/不変条件
TC-025: 本人重複/境界
TC-028: 法人整合/直接SQL
TC-029: 不変参照/直接SQL
TC-035: 登録/並行
TC-036: 法人独立/並行
TC-037: Repository検索/漏洩
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    CorporateMembership,
    StaffPersonLink,
)
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.infrastructure.corporate.postgres.corporate import PostgresCorporateRepository
from app.infrastructure.identity.postgres.account_person import (
    PostgresAccountPersonRepository,
)
from app.infrastructure.identity.postgres.corporate_membership import (
    PostgresCorporateMembershipRepository,
)
from app.infrastructure.identity.postgres.staff_person_link import (
    PostgresStaffPersonLinkRepository,
)
from app.infrastructure.identity.postgres.user_account import (
    PostgresUserAccountRepository,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import (
    corporate_memberships,
    operation_audits,
    staff_person_links,
    user_accounts,
)
from app.infrastructure.staff.postgres.staff import PostgresStaffRepository
from tests.factories.identity_factory import create_account_person, create_user_account
from tests.factories.staff_factory import create_staff
from tests.infrastructure.postgres.helpers import create_corporate


async def _create_saved_corporate(
    session_factory: async_sessionmaker[AsyncSession],
    name: str = "テスト法人",
) -> CorporateId:
    corporate = create_corporate(name=f"{name}-{uuid4().hex[:8]}")
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresCorporateRepository(work).save(corporate)
        await work.commit()
    return corporate.id


@pytest.mark.asyncio
async def test_TC023_同一法人内で本人_アカウント_メンバーシップ_スタッフリンクを保存復元できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corporate_id = await _create_saved_corporate(session_factory, "TC023法人")
    person = create_account_person(corporate_id=corporate_id)
    account = create_user_account(
        corporate_id=corporate_id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(f"subject:{uuid4()}"),
    )
    staff = create_staff(corporate_id=corporate_id)
    link = StaffPersonLink(
        id=staff.id,
        corporate_id=corporate_id,
        person_id=person.id,
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate_id,
        staff_id=staff.id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
    )

    # Act: 同一法人内で全集約を保存
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person)
        await PostgresStaffRepository(work).save(staff)
        await PostgresStaffPersonLinkRepository(work).save(link)
        await PostgresUserAccountRepository(work).save(account)
        await PostgresCorporateMembershipRepository(work).save(membership)
        await work.commit()

    # Assert: 別トランザクションで復元し、法人と関係が保持されていることを確認
    async with PostgresUnitOfWork(session_factory) as work:
        saved_person = await PostgresAccountPersonRepository(work).get(person.id)
        saved_account = await PostgresUserAccountRepository(work).get(account.id)
        saved_link = await PostgresStaffPersonLinkRepository(work).get(staff.id)
        saved_membership = await PostgresCorporateMembershipRepository(work).get(
            membership.id
        )

        assert saved_person is not None
        assert saved_person.corporate_id == corporate_id
        assert saved_account is not None
        assert saved_account.corporate_id == corporate_id
        assert saved_account.person_id == person.id
        assert saved_link is not None
        assert saved_link.corporate_id == corporate_id
        assert saved_link.person_id == person.id
        assert saved_membership is not None
        assert saved_membership.corporate_id == corporate_id
        assert saved_membership.account_id == account.id
        assert saved_membership.staff_id == staff.id


@pytest.mark.asyncio
async def test_TC025_同一法人の同一本人へ2件目のアカウント作成は一意制約で拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corporate_id = await _create_saved_corporate(session_factory, "TC025法人")
    person = create_account_person(corporate_id=corporate_id)
    account1 = create_user_account(
        corporate_id=corporate_id,
        person_id=person.id,
    )
    account2 = create_user_account(
        corporate_id=corporate_id,
        person_id=person.id,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person)
        await PostgresUserAccountRepository(work).save(account1)
        await work.commit()

    # Act & Assert: 同一法人の同一本人へ別IDのアカウント保存を試みる
    with pytest.raises(IdentityConflictError):
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresUserAccountRepository(work).save(account2)
            await work.commit()


@pytest.mark.asyncio
async def test_TC028_直接SQLでの異法人参照の保存はDB制約により拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corp_a = await _create_saved_corporate(session_factory, "法人A")
    corp_b = await _create_saved_corporate(session_factory, "法人B")
    person_a = create_account_person(corporate_id=corp_a)
    account_a = create_user_account(corporate_id=corp_a, person_id=person_a.id)
    staff_a = create_staff(corporate_id=corp_a)
    person_b = create_account_person(corporate_id=corp_b)

    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person_a)
        await PostgresAccountPersonRepository(work).save(person_b)
        await PostgresStaffRepository(work).save(staff_a)
        await PostgresUserAccountRepository(work).save(account_a)
        await work.commit()

    now = datetime.now(UTC)

    # 違反1: 法人Bのアカウントに法人Aの本人を直接紐付けようとする
    with pytest.raises((IntegrityError, DBAPIError)):
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                insert(user_accounts).values(
                    id=uuid4(),
                    corporate_id=corp_b.value,
                    person_id=person_a.id.value,
                    status=AccountStatus.ACTIVE.value,
                    external_subject=f"test:{uuid4()}",
                    payload={},
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await work.commit()

    # 違反2: 法人Bのメンバーシップに法人Aのアカウントを直接紐付けようとする
    with pytest.raises((IntegrityError, DBAPIError)):
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                insert(corporate_memberships).values(
                    id=uuid4(),
                    corporate_id=corp_b.value,
                    account_id=account_a.id.value,
                    role="store_operator",
                    status="active",
                    payload={},
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await work.commit()

    # 違反3: 法人Aのスタッフリンクに法人Bの本人を直接紐付けようとする
    with pytest.raises((IntegrityError, DBAPIError)):
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                insert(staff_person_links).values(
                    id=staff_a.id.value,
                    corporate_id=corp_a.value,
                    person_id=person_b.id.value,
                    payload={},
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await work.commit()

    # 違反4: 操作監査でアカウント所属法人と異なる法人IDを指定する
    with pytest.raises((IntegrityError, DBAPIError)):
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                insert(operation_audits).values(
                    id=uuid4(),
                    person_id=person_a.id.value,
                    account_id=account_a.id.value,
                    operation="test_operation",
                    resource_id=uuid4(),
                    corporate_id=corp_b.value,
                    recorded_at=now,
                )
            )
            await work.commit()


@pytest.mark.asyncio
async def test_TC029_直接SQLでの既存アカウントの法人_本人_外部主体の変更はトリガにより拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corp_a = await _create_saved_corporate(session_factory, "TC029法人A")
    corp_b = await _create_saved_corporate(session_factory, "TC029法人B")
    person_a1 = create_account_person(corporate_id=corp_a)
    person_a2 = create_account_person(corporate_id=corp_a)
    subject_initial = f"initial-subject-{uuid4()}"
    account = create_user_account(
        corporate_id=corp_a,
        person_id=person_a1.id,
        external_subject=ExternalSubjectKey(subject_initial),
    )
    staff = create_staff(corporate_id=corp_a)
    link = StaffPersonLink(
        id=staff.id,
        corporate_id=corp_a,
        person_id=person_a1.id,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person_a1)
        await PostgresAccountPersonRepository(work).save(person_a2)
        await PostgresStaffRepository(work).save(staff)
        await PostgresStaffPersonLinkRepository(work).save(link)
        await PostgresUserAccountRepository(work).save(account)
        await work.commit()

    # Act & Assert 1: アカウントの person_id 変更を直接SQLで試行
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                update(user_accounts)
                .where(user_accounts.c.id == account.id.value)
                .values(person_id=person_a2.id.value)
            )
            await work.commit()
    assert "ck_user_accounts_person_immutable" in str(
        exc_info.value
    ) or "アカウントの本人参照・法人・外部主体は変更できません。" in str(exc_info.value)

    # Act & Assert 2: アカウントの corporate_id 変更を直接SQLで試行
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                update(user_accounts)
                .where(user_accounts.c.id == account.id.value)
                .values(corporate_id=corp_b.value)
            )
            await work.commit()
    assert "ck_user_accounts_person_immutable" in str(
        exc_info.value
    ) or "アカウントの本人参照・法人・外部主体は変更できません。" in str(exc_info.value)

    # Act & Assert 3: アカウントの external_subject 変更を直接SQLで試行
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                update(user_accounts)
                .where(user_accounts.c.id == account.id.value)
                .values(external_subject=f"tampered-{uuid4()}")
            )
            await work.commit()
    assert "ck_user_accounts_person_immutable" in str(
        exc_info.value
    ) or "アカウントの本人参照・法人・外部主体は変更できません。" in str(exc_info.value)

    # Act & Assert 4: スタッフリンクの person_id 変更を直接SQLで試行
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        async with PostgresUnitOfWork(session_factory) as work:
            await work.session.execute(
                update(staff_person_links)
                .where(staff_person_links.c.id == staff.id.value)
                .values(person_id=person_a2.id.value)
            )
            await work.commit()
    assert "ck_staff_person_immutable" in str(
        exc_info.value
    ) or "本人対応は変更できません。" in str(exc_info.value)


@pytest.mark.asyncio
async def test_TC035_同一法人内でのアカウント重複保存の並行実行は1件のみ成功し片方は競合エラーになる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corporate_id = await _create_saved_corporate(session_factory, "TC035法人")
    person = create_account_person(corporate_id=corporate_id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person)
        await work.commit()

    barrier = asyncio.Barrier(2)

    async def save_account() -> UserAccountId:
        acc = create_user_account(
            corporate_id=corporate_id,
            person_id=person.id,
        )
        async with PostgresUnitOfWork(session_factory) as work:
            await barrier.wait()
            await PostgresUserAccountRepository(work).save(acc)
            await work.commit()
        return acc.id

    # Act: 2つの別トランザクションから同一人物のアカウントを並行作成
    results = await asyncio.wait_for(
        asyncio.gather(save_account(), save_account(), return_exceptions=True),
        timeout=15,
    )

    # Assert: 1件のみ成功し、もう1件は IdentityConflictError
    success_count = sum(isinstance(item, UserAccountId) for item in results)
    conflict_count = sum(isinstance(item, IdentityConflictError) for item in results)
    assert success_count == 1
    assert conflict_count == 1


@pytest.mark.asyncio
async def test_TC036_別法人であれば同本人や同外部主体のアカウントが並行して独立保存できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corp_a = await _create_saved_corporate(session_factory, "TC036法人A")
    corp_b = await _create_saved_corporate(session_factory, "TC036法人B")
    person_a = create_account_person(corporate_id=corp_a)
    person_b = create_account_person(corporate_id=corp_b)
    shared_subject = ExternalSubjectKey(f"subject:{uuid4()}")

    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person_a)
        await PostgresAccountPersonRepository(work).save(person_b)
        await work.commit()

    barrier = asyncio.Barrier(2)

    async def save_for(
        corp_id: CorporateId, person_id: AccountPersonId
    ) -> UserAccountId:
        acc = create_user_account(
            corporate_id=corp_id,
            person_id=person_id,
            external_subject=shared_subject,
        )
        async with PostgresUnitOfWork(session_factory) as work:
            await barrier.wait()
            await PostgresUserAccountRepository(work).save(acc)
            await work.commit()
        return acc.id

    # Act: 別法人で同一の外部主体を持つアカウントを並行保存
    results = await asyncio.wait_for(
        asyncio.gather(
            save_for(corp_a, person_a.id),
            save_for(corp_b, person_b.id),
            return_exceptions=True,
        ),
        timeout=15,
    )

    # Assert: 両方とも独立して成功する（法人横断一意制約に阻まれない）
    assert isinstance(results[0], UserAccountId)
    assert isinstance(results[1], UserAccountId)
    acc_a_id: UserAccountId = results[0]
    acc_b_id: UserAccountId = results[1]
    assert acc_a_id != acc_b_id

    async with PostgresUnitOfWork(session_factory) as work:
        repo = PostgresUserAccountRepository(work)
        acc_a = await repo.find_for_corporate(corp_a, acc_a_id)
        acc_b = await repo.find_for_corporate(corp_b, acc_b_id)
        assert acc_a is not None and acc_a.corporate_id == corp_a
        assert acc_b is not None and acc_b.corporate_id == corp_b


@pytest.mark.asyncio
async def test_TC037_法人スコープ検索において別法人のデータは存在せず漏洩しない(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    corp_a = await _create_saved_corporate(session_factory, "TC037法人A")
    corp_b = await _create_saved_corporate(session_factory, "TC037法人B")
    person_a = create_account_person(corporate_id=corp_a)
    person_b = create_account_person(corporate_id=corp_b)
    account_a = create_user_account(corporate_id=corp_a, person_id=person_a.id)
    account_b = create_user_account(corporate_id=corp_b, person_id=person_b.id)
    staff_a = create_staff(corporate_id=corp_a)
    staff_b = create_staff(corporate_id=corp_b)
    link_a = StaffPersonLink(id=staff_a.id, corporate_id=corp_a, person_id=person_a.id)
    link_b = StaffPersonLink(id=staff_b.id, corporate_id=corp_b, person_id=person_b.id)

    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresAccountPersonRepository(work).save(person_a)
        await PostgresAccountPersonRepository(work).save(person_b)
        await PostgresStaffRepository(work).save(staff_a)
        await PostgresStaffRepository(work).save(staff_b)
        await PostgresStaffPersonLinkRepository(work).save(link_a)
        await PostgresStaffPersonLinkRepository(work).save(link_b)
        await PostgresUserAccountRepository(work).save(account_a)
        await PostgresUserAccountRepository(work).save(account_b)
        await work.commit()

    # Act & Assert: 法人Aの条件で法人Bの本人・アカウント・リンクを検索
    async with PostgresUnitOfWork(session_factory) as work:
        people = PostgresAccountPersonRepository(work)
        accounts = PostgresUserAccountRepository(work)
        links = PostgresStaffPersonLinkRepository(work)

        # 1. 本人検索
        assert await people.find_for_corporate(corp_a, person_b.id) is None
        assert await people.find_for_corporate(corp_a, person_a.id) == person_a

        # 2. アカウント検索 (by id)
        assert await accounts.find_for_corporate(corp_a, account_b.id) is None
        assert await accounts.find_for_corporate(corp_a, account_a.id) == account_a

        # 3. アカウント検索 (by person)
        assert await accounts.get_by_person(corp_a, person_b.id) is None
        assert await accounts.get_by_person(corp_a, person_a.id) == account_a

        # 4. スタッフリンク検索
        assert await links.find_for_corporate(corp_a, staff_b.id) is None
        assert await links.find_for_corporate(corp_a, staff_a.id) == link_a
