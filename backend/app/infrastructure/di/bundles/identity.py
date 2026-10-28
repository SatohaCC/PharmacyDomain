"""本人確認境界から個人アカウント・法人アクセス権へ接続する。"""

from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock
from app.application.composition.commands.register_contract import (
    RegisterContractUseCase,
)
from app.application.composition.registry import IdentityUseCases
from app.application.corporate.commands.register_corporate import (
    RegisterCorporateUseCase,
)
from app.application.identity.commands.accept_invitation import AcceptInvitationUseCase
from app.application.identity.commands.cancel_invitation import CancelInvitationUseCase
from app.application.identity.commands.change_membership import ChangeMembershipUseCase
from app.application.identity.commands.invite_user import InviteUserUseCase
from app.application.identity.commands.link_staff_person import LinkStaffPersonUseCase
from app.application.identity.commands.reactivate_account import (
    ReactivateAccountUseCase,
)
from app.application.identity.commands.register_local_user import (
    RegisterLocalUserUseCase,
)
from app.application.identity.commands.register_person import RegisterPersonUseCase
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.commands.suspend_account import SuspendAccountUseCase
from app.application.identity.queries.get_invitation import GetInvitationUseCase
from app.application.identity.queries.get_user import GetUserUseCase
from app.application.identity.queries.list_users import ListUsersUseCase
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.corporate.services import CorporateNameUniquenessService
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from app.infrastructure.readers.identity_get_invitation import GetInvitationProjection
from app.infrastructure.readers.identity_get_user import GetUserProjection
from app.infrastructure.readers.identity_list_users import ListUsersProjection
from app.infrastructure.readers.identity_resolve_actor import ResolveActorProjection


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
        get_invitation=GetInvitationUseCase(
            reader=GetInvitationProjection(identity.invitations), access=access
        ),
        change_membership=ChangeMembershipUseCase(
            identity,
            repositories.staff,
            repositories.store,
            access,
            unit_of_work,
            lock,
        ),
        list_users=ListUsersUseCase(
            reader=ListUsersProjection(identity), access=access
        ),
        get_user=GetUserUseCase(reader=GetUserProjection(identity), access=access),
        suspend_account=SuspendAccountUseCase(identity, access, unit_of_work, lock),
        reactivate_account=ReactivateAccountUseCase(
            identity, access, unit_of_work, lock
        ),
        resolve_actor=ResolveActorUseCase(
            reader=ResolveActorProjection(
                identity.people, identity.accounts, identity.memberships
            )
        ),
    )
