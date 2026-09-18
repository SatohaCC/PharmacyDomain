"""管理薬剤師Repositoryが最後の防衛として守る期間競合。"""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import ManagerAssignmentConflictError
from app.domain.store.primitives import StoreId
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)


def _assignment() -> StoreManagerAssignment:
    return StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        staff_id=StaffId.generate(),
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 17)
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("same_store", [True, False], ids=["同店舗", "同スタッフ"])
@pytest.mark.parametrize(
    "starts_on,conflict",
    [(date(2026, 9, 17), True), (date(2026, 9, 18), False)],
    ids=["終了日と重複", "翌日開始"],
)
async def test_店舗とスタッフの任命は閉区間の重複を拒否する(
    same_store: bool, starts_on: date, conflict: bool
) -> None:
    repository = InMemoryStoreManagerAssignmentRepository()
    original = _assignment()
    await repository.save(original)
    candidate = replace(
        original,
        id=StoreManagerAssignmentId.generate(),
        store_id=original.store_id if same_store else StoreId.generate(),
        staff_id=StaffId.generate() if same_store else original.staff_id,
        period=ManagerAssignmentPeriod(starts_on=starts_on),
    )
    if conflict:
        with pytest.raises(ManagerAssignmentConflictError):
            await repository.save(candidate)
        assert await repository.get(candidate.id) is None
    else:
        await repository.save(candidate)
        assert await repository.get(candidate.id) == candidate
    assert await repository.get(original.id) == original


@pytest.mark.asyncio
async def test_自分自身の更新を重複任命として拒否しない() -> None:
    repository = InMemoryStoreManagerAssignmentRepository()
    original = _assignment()
    await repository.save(original)
    changed = replace(
        original, period=ManagerAssignmentPeriod(starts_on=original.period.starts_on)
    )
    await repository.save(changed)
    actual = await repository.get(original.id)
    assert actual is not None
    assert actual.period.ends_on is None


@pytest.mark.asyncio
async def test_取消した任命は新任命を妨げず履歴には残る() -> None:
    repository = InMemoryStoreManagerAssignmentRepository()
    cancelled = replace(_assignment(), status=ManagerAssignmentStatus.CANCELLED)
    await repository.save(cancelled)
    current = replace(
        cancelled,
        id=StoreManagerAssignmentId.generate(),
        status=ManagerAssignmentStatus.CONFIRMED,
    )
    await repository.save(current)
    assert {
        item.id
        for item in await repository.list_by_store(
            current.corporate_id, current.store_id
        )
    } == {cancelled.id, current.id}
