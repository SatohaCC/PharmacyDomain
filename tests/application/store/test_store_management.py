"""店舗状態変更と管理薬剤師履歴を同じ業務日で扱う。"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.access_control import ActorRole, AuthorizationService
from app.application.access_control.models import ResolvedActorContext
from app.application.corporate import CorporateAccessService
from app.application.store.management import (
    ChangeStoreStatusCommand,
    ChangeStoreStatusUseCase,
)
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.staff.primitives import StaffId
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import (
    FakeOrganizationLock,
    FakeStoreWorkBoundary,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


@pytest.mark.asyncio
@pytest.mark.parametrize("unfinished", [False, True])
async def test_閉局時の残業務確認と任命整理を日本の業務日で行う(
    unfinished: bool,
) -> None:
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)
    managers = InMemoryStoreManagerAssignmentRepository()
    current = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=store.corporate_id,
        store_id=store.id,
        staff_id=StaffId.generate(),
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 30)
        ),
    )
    future = replace(
        current,
        id=StoreManagerAssignmentId.generate(),
        period=ManagerAssignmentPeriod(starts_on=date(2026, 10, 1)),
    )
    past = replace(
        current,
        id=StoreManagerAssignmentId.generate(),
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31)
        ),
    )
    for item in [past, current, future]:
        await managers.save(item)
    actor = ResolvedActorContext(
        principal_id="管理者",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )
    now = datetime(2026, 9, 17, 16, tzinfo=UTC)
    lock = FakeOrganizationLock()
    use_case = ChangeStoreStatusUseCase(
        stores,
        managers,
        FakeStoreWorkBoundary(unfinished),
        CorporateAccessService(
            AutoProvisioningCorporateRepository(), AuthorizationService(actor)
        ),
        FakeClock(now),
        NullUnitOfWork(),
        lock,
    )
    command = ChangeStoreStatusCommand(
        corporate_id=str(store.corporate_id.value),
        store_id=str(store.id.value),
        status=StoreStatus.CLOSED,
        reason="営業終了",
    )
    if unfinished:
        with pytest.raises(DomainError):
            await use_case.execute(command)
        actual = await stores.get(store.id)
        assert actual is not None and actual.status == StoreStatus.ACTIVE
        unchanged = await managers.get(current.id)
        assert unchanged is not None and unchanged.period == current.period
    else:
        result = await use_case.execute(command)
        assert result.status == StoreStatus.CLOSED
        assert result.status_history[0].person_id == str(actor.person_id.value)
        assert result.status_history[0].account_id == str(actor.account_id.value)
        assert result.status_history[0].recorded_at == now
        ended = await managers.get(current.id)
        cancelled = await managers.get(future.id)
        assert ended is not None and ended.period.ends_on == date(2026, 9, 18)
        assert (
            cancelled is not None
            and cancelled.status == ManagerAssignmentStatus.CANCELLED
        )
        assert await managers.get(past.id) == past
        repeated = await use_case.execute(command)
        assert len(repeated.status_history) == 1
    assert lock.keys
