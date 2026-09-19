"""Identityのユースケースを、インメモリの保存境界で組み立てる補助。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.identity.accept_invitation import AcceptInvitationUseCase
from app.application.identity.cancel_invitation import CancelInvitationUseCase
from app.application.identity.change_account_status import (
    ReactivateAccountUseCase,
    SuspendAccountUseCase,
)
from app.application.identity.change_membership import ChangeMembershipUseCase
from app.application.identity.get_invitation import GetInvitationUseCase
from app.application.identity.get_user import GetUserUseCase
from app.application.identity.invite_user import InviteUserUseCase
from app.application.identity.link_staff import LinkStaffPersonUseCase
from app.application.identity.list_users import ListUsersUseCase
from app.application.identity.register_person import RegisterPersonUseCase
from app.application.identity.support import IdentityRepositories
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
    InMemoryUserInvitationRepository,
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
    invite: InviteUserUseCase
    accept: AcceptInvitationUseCase
    cancel_invitation: CancelInvitationUseCase
    get_invitation: GetInvitationUseCase
    change_membership: ChangeMembershipUseCase
    list_users: ListUsersUseCase
    get_user: GetUserUseCase
    suspend_account: SuspendAccountUseCase
    reactivate_account: ReactivateAccountUseCase


def create_identity_use_cases(*, now: datetime | None = None) -> IdentityUseCaseSet:
    """本番と同じ引数構成でユースケースを組み立てる。"""
    repositories = IdentityRepositories(
        InMemoryAccountPersonRepository(),
        InMemoryUserAccountRepository(),
        InMemoryCorporateMembershipRepository(),
        InMemoryStaffPersonLinkRepository(),
        InMemoryUserInvitationRepository(),
    )
    staff = InMemoryStaffRepository()
    stores = InMemoryStoreRepository()
    clock = FakeClock(now if now is not None else datetime(2026, 9, 17, tzinfo=UTC))
    access = create_vendor_corporate_access()
    work = NullUnitOfWork()
    lock = FakeOrganizationLock()
    return IdentityUseCaseSet(
        repositories=repositories,
        staff=staff,
        stores=stores,
        clock=clock,
        register_person=RegisterPersonUseCase(repositories.people, access, work),
        link_staff=LinkStaffPersonUseCase(
            repositories.people, repositories.links, staff, access, work, lock
        ),
        invite=InviteUserUseCase(
            repositories, staff, stores, access, clock, work, lock
        ),
        accept=AcceptInvitationUseCase(
            repositories,
            staff,
            stores,
            AutoProvisioningCorporateRepository(),
            clock,
            work,
            lock,
        ),
        cancel_invitation=CancelInvitationUseCase(
            repositories.invitations, access, work, lock
        ),
        get_invitation=GetInvitationUseCase(repositories.invitations, access),
        change_membership=ChangeMembershipUseCase(
            repositories, staff, stores, access, work, lock
        ),
        list_users=ListUsersUseCase(repositories, access),
        get_user=GetUserUseCase(repositories, access),
        suspend_account=SuspendAccountUseCase(repositories, access, work, lock),
        reactivate_account=ReactivateAccountUseCase(repositories, access, work, lock),
    )


__all__ = ["IdentityUseCaseSet", "create_identity_use_cases"]
