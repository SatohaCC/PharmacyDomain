"""本人確認境界から個人アカウント・法人アクセス権へ接続する。"""

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary
from app.application.common.clock import Clock
from app.application.identity.management import (
    IdentityManagementUseCase,
    IdentityRepositories,
)
from app.application.identity.resolve_actor import ResolveActorUseCase
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization import PostgresOrganizationLock
from app.infrastructure.postgres.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class IdentityUseCases:
    """本人・アカウント管理と最新の権限解決。"""

    management: IdentityManagementUseCase
    resolve_actor: ResolveActorUseCase


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
    return IdentityUseCases(
        management=IdentityManagementUseCase(
            identity,
            repositories.staff,
            repositories.store,
            access,
            clock,
            unit_of_work,
            PostgresOrganizationLock(unit_of_work),
            repositories.corporate,
        ),
        resolve_actor=ResolveActorUseCase(
            identity.people, identity.accounts, identity.memberships
        ),
    )
