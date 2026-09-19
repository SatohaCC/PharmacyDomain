"""管理薬剤師Repositoryが守る期間競合と、在任の引き当て。"""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
)
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
        person_id=AccountPersonId.generate(),
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 17)
        ),
    )


#: 期間の境界。任命期間は終了日を含む閉区間なので、終了日当日に始めると重なる。
_BOUNDARY_DAYS = [(date(2026, 9, 17), True), (date(2026, 9, 18), False)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "starts_on,conflict", _BOUNDARY_DAYS, ids=["終了日と重複", "翌日開始"]
)
async def test_同じ店舗に期間の重なる管理薬剤師を2人置けない(
    starts_on: date, conflict: bool
) -> None:
    """薬局に置く管理薬剤師は、どの時点でも1人である。"""
    repository = InMemoryStoreManagerAssignmentRepository()
    original = _assignment()
    await repository.save(original)
    candidate = replace(
        original,
        id=StoreManagerAssignmentId.generate(),
        staff_id=StaffId.generate(),
        person_id=AccountPersonId.generate(),
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
@pytest.mark.parametrize(
    "starts_on,conflict", _BOUNDARY_DAYS, ids=["終了日と重複", "翌日開始"]
)
async def test_同じ人物は期間の重なる複数店舗の管理薬剤師を兼ねられない(
    starts_on: date, conflict: bool
) -> None:
    """専任義務は自然人にかかるので、法人が違っても兼務は成立しない。

    法人ごとにスタッフを持てる以上、鍵をスタッフIDにすると、グループ内の別法人
    どうしで同じ人物が両方の管理薬剤師になれてしまう。ここでは法人・店舗・
    スタッフをすべて別にして、本人だけを揃える。
    """
    repository = InMemoryStoreManagerAssignmentRepository()
    original = _assignment()
    await repository.save(original)
    candidate = replace(
        original,
        id=StoreManagerAssignmentId.generate(),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        staff_id=StaffId.generate(),
        period=ManagerAssignmentPeriod(starts_on=starts_on),
    )
    if conflict:
        with pytest.raises(ManagerExclusiveDutyConflictError):
            await repository.save(candidate)
        assert await repository.get(candidate.id) is None
    else:
        await repository.save(candidate)
        assert await repository.get(candidate.id) == candidate
    assert await repository.get(original.id) == original


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "as_of,found",
    [
        (date(2026, 8, 31), False),
        (date(2026, 9, 1), True),
        (date(2026, 9, 17), True),
        (date(2026, 9, 18), False),
    ],
    ids=["開始前日", "開始日", "終了日", "終了翌日"],
)
async def test_在任の引き当ては終了日を含む閉区間で判定する(
    as_of: date, found: bool
) -> None:
    """業務可否の判定はこの引き当てだけを見るので、境界日を実装ごとに固定する。

    永続化実装では ``daterange`` の含有演算に委ねる。閉区間として保存しないと
    終了日当日の調剤が拒否されるが、その食い違いはDBに繋ぐまで現れない。
    """
    repository = InMemoryStoreManagerAssignmentRepository()
    assignment = _assignment()
    await repository.save(assignment)
    actual = await repository.find_effective(
        assignment.corporate_id, assignment.store_id, as_of
    )
    assert (actual == assignment) is found


@pytest.mark.asyncio
async def test_取消した任命は在任として引き当てられない() -> None:
    """取消は履歴として残るが、在任の有無には数えない。"""
    repository = InMemoryStoreManagerAssignmentRepository()
    cancelled = replace(_assignment(), status=ManagerAssignmentStatus.CANCELLED)
    await repository.save(cancelled)
    assert (
        await repository.find_effective(
            cancelled.corporate_id, cancelled.store_id, cancelled.period.starts_on
        )
        is None
    )


@pytest.mark.asyncio
async def test_他法人からは在任を引き当てられない() -> None:
    """店舗IDを知っていても、法人が違えば存在を見せない。"""
    repository = InMemoryStoreManagerAssignmentRepository()
    assignment = _assignment()
    await repository.save(assignment)
    assert (
        await repository.find_effective(
            CorporateId.generate(), assignment.store_id, assignment.period.starts_on
        )
        is None
    )


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
