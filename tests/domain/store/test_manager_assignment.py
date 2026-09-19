"""管理薬剤師の期間境界と取消履歴。"""

from datetime import date

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.staff.primitives import StaffId
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    ManagerAssignmentStatus,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.primitives import StoreId


def _assignment() -> StoreManagerAssignment:
    return StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        staff_id=StaffId.generate(),
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 10, 1), ends_on=date(2026, 10, 31)
        ),
    )


def test_任命の終了日を開始日より前にできない() -> None:
    with pytest.raises(DomainValidationError):
        ManagerAssignmentPeriod(starts_on=date(2026, 10, 1), ends_on=date(2026, 9, 30))


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (date(2026, 9, 30), False),
        (date(2026, 10, 1), True),
        (date(2026, 10, 31), True),
        (date(2026, 11, 1), False),
    ],
)
def test_任命の適用期間は終了日を含む(target: date, expected: bool) -> None:
    assert _assignment().is_effective_on(target) is expected


def test_開始前に取り消した任命は_履歴を保ち有効任命から外れる() -> None:
    assignment = _assignment()

    cancelled = assignment.cancel(applied_on=date(2026, 9, 30))

    assert cancelled.id == assignment.id
    assert cancelled.period == assignment.period
    assert cancelled.status == ManagerAssignmentStatus.CANCELLED
    assert not cancelled.is_effective_on(date(2026, 10, 1))
    assert assignment.status == ManagerAssignmentStatus.CONFIRMED


@pytest.mark.parametrize("day", [date(2026, 10, 1), date(2026, 10, 2)])
def test_開始当日以降の任命を取消できない(day: date) -> None:
    with pytest.raises(DomainError):
        _assignment().cancel(applied_on=day)


def test_任命を終了しても終了日当日は有効である() -> None:
    ended = _assignment().end(ends_on=date(2026, 10, 15))
    assert ended.is_effective_on(date(2026, 10, 15))
    assert not ended.is_effective_on(date(2026, 10, 16))


def test_開始前の日を任命終了日として指定できない() -> None:
    with pytest.raises(DomainError):
        _assignment().end(ends_on=date(2026, 9, 30))
