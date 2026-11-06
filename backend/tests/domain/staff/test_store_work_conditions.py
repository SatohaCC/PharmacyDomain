"""店舗別の週時間数と適用・訂正履歴。"""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.primitives import (
    StoreDuty,
    WeeklyStoreHours,
    WorkConditionRecorder,
)
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    StoreAffiliation,
    StoreWorkCondition,
)
from app.domain.store.identifiers import StoreId
from tests.factories.staff_factory import create_staff


def test_店舗勤務条件_複数店舗と同日訂正の場合_店舗別の適用履歴を保持する() -> None:
    # Arrange
    a, b = StoreId.generate(), StoreId.generate()
    staff = replace(
        create_staff(),
        affiliations=tuple(
            StoreAffiliation(
                store_id=store,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=store == a,
            )
            for store in (a, b)
        ),
    )

    def condition(store: StoreId, hours: str, starts: date) -> StoreWorkCondition:
        return StoreWorkCondition(
            store_id=store,
            effective_from=starts,
            weekly_hours=WeeklyStoreHours(Decimal(hours)),
            duty=StoreDuty.OTHER,
            recorded_at=datetime(2026, 11, 2, tzinfo=UTC),
            recorded_by=WorkConditionRecorder("運営者"),
        )

    # Act
    staff = staff.record_work_conditions(
        (condition(a, "32", date(2026, 1, 1)),), applied_on=date(2026, 11, 3)
    )
    staff = staff.record_work_conditions(
        (condition(b, "8", date(2026, 1, 1)),), applied_on=date(2026, 11, 3)
    )
    staff = staff.record_work_conditions(
        (condition(a, "30.5", date(2026, 11, 1)),), applied_on=date(2026, 11, 3)
    )
    staff = staff.record_work_conditions(
        (condition(a, "31", date(2026, 11, 1)),), applied_on=date(2026, 11, 3)
    )
    # Assert
    old = staff.work_condition_on(a, date(2026, 10, 31))
    current = staff.work_condition_on(a, date(2026, 11, 1))
    other = staff.work_condition_on(b, date(2026, 11, 1))
    assert (
        old is not None
        and old.weekly_hours is not None
        and old.weekly_hours.value == Decimal("32")
    )
    assert (
        current is not None
        and current.weekly_hours is not None
        and current.weekly_hours.value == Decimal("31")
    )
    assert (
        other is not None
        and other.weekly_hours is not None
        and other.weekly_hours.value == Decimal("8")
    )
    assert len(staff.work_conditions) == 4


@pytest.mark.parametrize("raw", ["-0.01", "168.01", "0.001", "NaN", "Infinity"])
def test_店舗週勤務時間_範囲や精度が不正な場合_拒否する(raw: str) -> None:
    with pytest.raises(DomainValidationError):
        WeeklyStoreHours(Decimal(raw))


@pytest.mark.parametrize("raw", ["0", "0.01", "32.5", "168"])
def test_店舗週勤務時間_許容範囲の場合_十進数を保つ(raw: str) -> None:
    assert WeeklyStoreHours(Decimal(raw)).value == Decimal(raw)


def test_店舗週勤務時間_合計が契約時間を超える場合_将来の変更も拒否する() -> None:
    from app.domain.staff.primitives import WeeklyContractHours

    a, b = StoreId.generate(), StoreId.generate()
    staff = replace(
        create_staff(),
        weekly_contract_hours=WeeklyContractHours(Decimal("40")),
        affiliations=tuple(
            StoreAffiliation(
                store_id=store,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=store == a,
            )
            for store in (a, b)
        ),
    )

    def condition(store: StoreId, hours: str, starts: date) -> StoreWorkCondition:
        return StoreWorkCondition(
            store_id=store,
            effective_from=starts,
            weekly_hours=WeeklyStoreHours(Decimal(hours)),
            duty=StoreDuty.OTHER,
            recorded_at=datetime(2026, 11, 3, tzinfo=UTC),
            recorded_by=WorkConditionRecorder("運営者"),
        )

    staff = staff.record_work_conditions(
        (condition(a, "32", date(2026, 1, 1)), condition(b, "8", date(2026, 1, 1))),
        applied_on=date(2026, 11, 3),
    )
    with pytest.raises(DomainValidationError, match="合計"):
        staff.record_work_conditions(
            (condition(b, "8.01", date(2026, 12, 1)),), applied_on=date(2026, 11, 3)
        )
    # 二店舗の配分をまとめて変える場合は、途中の合計ではなく変更後で判定する。
    staff = staff.record_work_conditions(
        (condition(a, "34", date(2026, 11, 3)), condition(b, "6", date(2026, 11, 3))),
        applied_on=date(2026, 11, 3),
    )
    # 契約時間を下げる場合も現在の合計を再検証する。
    with pytest.raises(DomainValidationError, match="合計"):
        staff.change_weekly_contract_hours(
            WeeklyContractHours(Decimal("39.99")), applied_on=date(2026, 11, 3)
        )
