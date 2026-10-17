"""退職時の権限停止を、インメモリの保存境界で組み立てる補助。"""

from __future__ import annotations

from app.application.composition.staff_integrity import StaffAccessRevocationService
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)


def create_access_revocation(
    memberships: InMemoryCorporateMembershipRepository | None = None,
    accounts: InMemoryUserAccountRepository | None = None,
) -> StaffAccessRevocationService:
    """権限停止サービスを組み立てる。台帳を渡さなければ空で作る。"""
    return StaffAccessRevocationService(
        memberships
        if memberships is not None
        else InMemoryCorporateMembershipRepository(),
        accounts if accounts is not None else InMemoryUserAccountRepository(),
        FakeOrganizationLock(),
    )
