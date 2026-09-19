"""組織管理の実DBテストで本人・雇用・権限を明示的に構築する。"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.domain.corporate.corporate import Corporate
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.staff.staff import Staff
from app.domain.store.store import Store
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.test_identity_persistence import _person


def external_subject_of(index: int) -> str:
    """本人確認基盤が返す主体識別子。

    ``ResolveActorUseCase`` は ``external_subject`` が未固定のアカウントを解決
    しない。HTTP経由のテストが渡す ``principal_id`` はこれと一致する必要があるので、
    両方をこの1関数から作り、片方だけ書き換えても気づけない状態にしない。
    """
    return f"issuer/person-{index}"


@dataclass
class Organization:
    """実在するベンダー本人と二名の法人管理者。"""

    root: PostgresCompositionRoot
    authorization: AuthorizationService
    corporate: Corporate
    store: Store
    staff: list[Staff]
    accounts: list[UserAccount]
    memberships: list[CorporateMembership]


async def setup_organization(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession]
) -> Organization:
    """テスト対象以外の参照不備が失敗原因にならない構成を保存する。"""
    corporate = create_corporate()
    store = create_store(corporate_id=corporate.id)
    people = [_person() for _ in range(3)]
    accounts = [
        UserAccount(
            id=UserAccountId.generate(),
            person_id=person.id,
            external_subject=ExternalSubjectKey(external_subject_of(index)),
            is_vendor_admin=index == 2,
        )
        for index, person in enumerate(people)
    ]
    staff = [
        replace(
            create_staff(corporate_id=corporate.id),
            qualifications=StaffQualifications.from_profiles(
                PharmacistProfile(
                    license_number=PharmacistLicenseNumber(str(123456 + index))
                )
            ),
            affiliations=(
                StoreAffiliation(
                    store_id=store.id,
                    is_primary=True,
                    period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                ),
            ),
        )
        for index in range(2)
    ]
    memberships = [
        CorporateMembership(
            id=CorporateMembershipId.generate(),
            account_id=accounts[index].id,
            corporate_id=corporate.id,
            role=MembershipRole.CORPORATE_ADMIN,
            staff_id=person.id,
            store_ids=frozenset(),
        )
        for index, person in enumerate(staff)
    ]
    async with PostgresUnitOfWork(factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store)
        for person, account in zip(people, accounts, strict=True):
            await repos.account_person.save(person)
            await repos.user_account.save(account)
        for index, employee in enumerate(staff):
            await repos.staff.save(employee)
            await repos.staff_person_link.save(
                StaffPersonLink(
                    id=employee.id,
                    corporate_id=corporate.id,
                    person_id=people[index].id,
                )
            )
            await repos.membership.save(memberships[index])
        await work.commit()
    authorization = AuthorizationService(
        ResolvedActorContext(
            principal_id="検証済みベンダー",
            roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            person_id=people[2].id,
            account_id=accounts[2].id,
        )
    )
    root = PostgresCompositionRoot(
        engine, factory, FakeClock(datetime(2026, 9, 17, 3, tzinfo=UTC))
    )
    return Organization(
        root, authorization, corporate, store, staff, accounts[:2], memberships
    )
