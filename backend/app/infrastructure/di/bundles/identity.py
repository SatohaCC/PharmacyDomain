"""本人確認境界から個人アカウント・法人アクセス権へ接続する。"""

from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock
from app.application.composition.adapters.contract_admin import (
    ContractAdminAdapter,
)
from app.application.composition.adapters.organization_snapshot_mapping import (
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_creator import StaffCreationAdapter
from app.application.composition.commands.register_contract import (
    RegisterContractUseCase,
)
from app.application.composition.registry import IdentityUseCases
from app.application.corporate.commands.register_corporate import (
    RegisterCorporateUseCase,
)
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
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.infrastructure.di.repositories import (
    PostgresRepositorySet,
)
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
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
        repositories.vendor_operator,
    )
    lock = PostgresOrganizationLock(unit_of_work)
    person = RegisterPersonUseCase(identity.people, access, unit_of_work)
    contract_admin = ContractAdminAdapter(
        accounts=identity.accounts,
        memberships=identity.memberships,
        credentials=PostgresCredentialWriter(unit_of_work),
    )
    contract = RegisterContractUseCase(
        RegisterCorporateUseCase(
            repositories.corporate,
            CorporateNameUniquenessService(repositories.corporate),
            access,
        ),
        person,
        contract_admin,
        unit_of_work,
    )
    staff_creator = StaffCreationAdapter(
        staff_repository=repositories.staff,
        store_repository=StaffStoreAdapter(repositories.store),
        uniqueness_service=StaffCodeUniquenessService(repositories.staff),
        assignment_service=StaffStoreAssignmentService(),
    )
    register_staff_for_admin = RegisterStaffForAdminUseCase(
        repositories=identity,
        corporate_access=access,
        staff_creator=staff_creator,
        unit_of_work=unit_of_work,
        lock=lock,
    )
    return IdentityUseCases(
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
        change_membership=ChangeMembershipUseCase(
            identity,
            repositories.staff,
            repositories.store,
            access,
            unit_of_work,
            lock,
            repositories.manager_assignment,
            clock,
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
                identity.people,
                identity.accounts,
                identity.memberships,
                repositories.manager_assignment,
                identity.vendor_operators,
                repositories.staff,
                repositories.store,
            ),
            clock=clock,
        ),
        register_staff_for_admin=register_staff_for_admin,
    )
