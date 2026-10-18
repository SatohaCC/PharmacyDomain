"""本人確認境界から個人アカウント・法人アクセス権へ接続する。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.common.clock import Clock
from app.application.composition.register_contract import RegisterContractUseCase
from app.application.composition.use_case_bundles import IdentityUseCases
from app.application.corporate.register_corporate import RegisterCorporateUseCase
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
from app.application.identity.register_local_user import RegisterLocalUserUseCase
from app.application.identity.register_person import RegisterPersonUseCase
from app.application.identity.resolve_actor import ResolveActorUseCase
from app.application.identity.support import IdentityRepositories
from app.domain.corporate.services import CorporateNameUniquenessService
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock


def build_identity_use_cases(
    repositories: PostgresRepositorySet,
    access: CorporateAccessBoundary,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> IdentityUseCases:
    """同じUoWの保存境界で本人とアクセス権を組み立てる。"""
    identity = IdentityRepositories(
        repositories.account_person,
        repositories.user_account,
        repositories.membership,
        repositories.staff_person_link,
        repositories.invitation,
    )
    lock = PostgresOrganizationLock(unit_of_work)
    person = RegisterPersonUseCase(identity.people, access, unit_of_work)
    local_user = RegisterLocalUserUseCase(
        identity,
        repositories.staff,
        repositories.store,
        access,
        unit_of_work,
        lock,
        PostgresCredentialWriter(unit_of_work),
    )
    contract = RegisterContractUseCase(
        RegisterCorporateUseCase(
            repositories.corporate,
            CorporateNameUniquenessService(repositories.corporate),
            access,
        ),
        person,
        local_user,
        unit_of_work,
    )
    return IdentityUseCases(
        register_local_user=local_user,
        register_contract=contract,
        register_person=RegisterPersonUseCase(identity.people, access, unit_of_work),
        link_staff=LinkStaffPersonUseCase(
            identity.people,
            identity.links,
            repositories.staff,
            access,
            unit_of_work,
            lock,
        ),
        invite=InviteUserUseCase(
            identity,
            repositories.staff,
            repositories.store,
            access,
            clock,
            unit_of_work,
            lock,
        ),
        accept=AcceptInvitationUseCase(
            identity,
            repositories.staff,
            repositories.store,
            repositories.corporate,
            clock,
            unit_of_work,
            lock,
        ),
        cancel_invitation=CancelInvitationUseCase(
            identity.invitations, access, unit_of_work, lock
        ),
        get_invitation=GetInvitationUseCase(identity.invitations, access),
        change_membership=ChangeMembershipUseCase(
            identity,
            repositories.staff,
            repositories.store,
            access,
            unit_of_work,
            lock,
        ),
        list_users=ListUsersUseCase(identity, access),
        get_user=GetUserUseCase(identity, access),
        suspend_account=SuspendAccountUseCase(identity, access, unit_of_work, lock),
        reactivate_account=ReactivateAccountUseCase(
            identity, access, unit_of_work, lock
        ),
        resolve_actor=ResolveActorUseCase(
            identity.people, identity.accounts, identity.memberships
        ),
    )
