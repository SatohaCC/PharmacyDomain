"""Identityのユースケースを、インメモリの保存境界で組み立てる補助。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.composition.adapters.organization_snapshot_mapping import (
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_creator import StaffCreationAdapter
from app.application.identity.commands.change_membership import ChangeMembershipUseCase
from app.application.identity.commands.link_staff_person import LinkStaffPersonUseCase
from app.application.identity.commands.reactivate_account import (
    ReactivateAccountUseCase,
)
from app.application.identity.commands.register_person import RegisterPersonUseCase
from app.application.identity.commands.register_staff_for_admin import (
    RegisterStaffForAdminUseCase,
)
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.suspend_account import SuspendAccountUseCase
from app.application.identity.queries.get_user import GetUserUseCase
from app.application.identity.queries.list_users import ListUsersUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import AccountPerson
from app.domain.shared.actor import AccountPersonId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.infrastructure.readers.identity_get_user import GetUserProjection
from app.infrastructure.readers.identity_list_users import ListUsersProjection
from tests.application.access_helpers import (
    create_vendor_corporate_access,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
    InMemoryVendorOperatorRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


@dataclass(frozen=True)
class IdentityUseCaseSet:
    """1つのUoWと保存境界を共有するIdentityのユースケース一式。"""

    repositories: IdentityRepositories
    staff: InMemoryStaffRepository
    stores: InMemoryStoreRepository
    clock: FakeClock
    register_person: RegisterPersonUseCase
    link_staff: LinkStaffPersonUseCase
    change_membership: ChangeMembershipUseCase
    list_users: ListUsersUseCase
    get_user: GetUserUseCase
    suspend_account: SuspendAccountUseCase
    reactivate_account: ReactivateAccountUseCase
    register_staff_for_admin: RegisterStaffForAdminUseCase


def create_identity_use_cases(*, now: datetime | None = None) -> IdentityUseCaseSet:
    """本番と同じ引数構成でユースケースを組み立てる。"""
    repositories = IdentityRepositories(
        InMemoryAccountPersonRepository(),
        InMemoryUserAccountRepository(),
        InMemoryCorporateMembershipRepository(),
        InMemoryStaffPersonLinkRepository(),
        InMemoryVendorOperatorRepository(),
    )
    staff = InMemoryStaffRepository()
    stores = InMemoryStoreRepository()
    clock = FakeClock(now if now is not None else datetime(2026, 9, 17, tzinfo=UTC))
    access = create_vendor_corporate_access()
    work = NullUnitOfWork()
    lock = FakeOrganizationLock()
    staff_creator = StaffCreationAdapter(
        staff_repository=staff,
        store_repository=StaffStoreAdapter(stores),
        uniqueness_service=StaffCodeUniquenessService(staff),
        assignment_service=StaffStoreAssignmentService(),
    )
    return IdentityUseCaseSet(
        repositories=repositories,
        staff=staff,
        stores=stores,
        clock=clock,
        register_person=RegisterPersonUseCase(repositories.people, access, work),
        link_staff=LinkStaffPersonUseCase(
            repositories.people, repositories.links, staff, access, work, lock
        ),
        change_membership=ChangeMembershipUseCase(
            repositories,
            staff,
            stores,
            access,
            work,
            lock,
            InMemoryStoreManagerAssignmentRepository(),
            clock,
        ),
        list_users=ListUsersUseCase(
            reader=ListUsersProjection(repositories), access=access
        ),
        get_user=GetUserUseCase(reader=GetUserProjection(repositories), access=access),
        suspend_account=SuspendAccountUseCase(repositories, access, work, lock),
        reactivate_account=ReactivateAccountUseCase(repositories, access, work, lock),
        register_staff_for_admin=RegisterStaffForAdminUseCase(
            repositories, access, staff_creator, work, lock
        ),
    )


@dataclass
class _CommandStub:
    corporate_id: str
    person_id: str


@dataclass
class IdentityTestFixture:
    """テスト用のIdentityコンテキスト一式。"""

    service: IdentityUseCaseSet
    repositories: IdentityRepositories
    clock: FakeClock
    person: AccountPerson
    command: _CommandStub


def create_person(corporate_id: CorporateId, last_name: str = "山田") -> AccountPerson:
    return AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart(last_name), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
    )


async def _setup() -> IdentityTestFixture:
    service = create_identity_use_cases()
    corporate_id = CorporateId.generate()
    person = create_person(corporate_id)
    await service.repositories.people.save(person)
    command = _CommandStub(
        corporate_id=str(corporate_id.value),
        person_id=str(person.id.value),
    )
    return IdentityTestFixture(
        service, service.repositories, service.clock, person, command
    )


__all__ = [
    "IdentityUseCaseSet",
    "IdentityTestFixture",
    "create_identity_use_cases",
    "_setup",
]
