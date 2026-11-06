"""勤務条件変更時に保存済みの権限を再照合する。"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.common.exceptions import AuthorizationError
from app.application.composition.adapters.work_condition_management import (
    WorkConditionManagementGuard,
)
from app.domain.identity.primitives import AccountStatus, MembershipRole
from tests.factories.identity_factory import (
    create_corporate_membership,
    create_user_account,
)
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["account", "membership", "role", "none"])
async def test_勤務条件変更権限_本人解決後の権限変更_保存時点の状態を反映する(
    change: str,
) -> None:
    # Arrange
    store = create_store()
    account = create_user_account(corporate_id=store.corporate_id)
    membership = create_corporate_membership(
        corporate_id=store.corporate_id,
        account_id=account.id,
        role=MembershipRole.CORPORATE_ADMIN,
    )
    actor = ResolvedActorContext(
        principal_id="テスト管理者",
        person_id=account.person_id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=store.corporate_id,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
    )
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    await accounts.save(
        replace(account, status=AccountStatus.SUSPENDED)
        if change == "account"
        else account
    )
    if change == "membership":
        membership = replace(membership, status=AccountStatus.SUSPENDED)
    elif change == "role":
        from app.domain.staff.identifiers import StaffId

        membership = replace(
            membership, role=MembershipRole.MEMBER, staff_id=StaffId.generate()
        )
    await memberships.save(membership)
    guard = WorkConditionManagementGuard(
        actor,
        accounts,
        memberships,
        InMemoryStaffRepository(),
        InMemoryStoreManagerAssignmentRepository(),
        FakeClock(datetime(2026, 11, 2, tzinfo=UTC)),
    )

    # Act / Assert
    if change == "none":
        await guard.require_current(store.corporate_id, store.id)
    else:
        with pytest.raises(AuthorizationError):
            await guard.require_current(store.corporate_id, store.id)
