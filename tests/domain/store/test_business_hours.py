"""開局時間の時間帯・曜日・特例日の契約。"""

from dataclasses import replace
from datetime import UTC, date, time

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.business_hours import (
    BusinessDayException,
    BusinessHours,
    BusinessHourSlot,
    BusinessHoursNote,
    BusinessWeekday,
    StoreOpeningState,
    WeekdayBusinessHours,
    weekday_of,
)
from app.domain.store.lifecycle import StoreStatus
from tests.factories.store_factory import create_store

#: 平日の標準的な開局。昼休みで2つに分かれる。
_MORNING = BusinessHourSlot(opens_at=time(9, 0), closes_at=time(13, 0))
_AFTERNOON = BusinessHourSlot(opens_at=time(14, 0), closes_at=time(19, 0))

#: 2026-09-17 は木曜、2026-09-20 は日曜。
_THURSDAY = date(2026, 9, 17)
_SUNDAY = date(2026, 9, 20)

#: 曜日番号と曜日の対応。実装の表とは独立に、実在する日付から書く。
_WEEKDAY_SAMPLES: dict[date, BusinessWeekday] = {
    date(2026, 9, 14): BusinessWeekday.MONDAY,
    date(2026, 9, 15): BusinessWeekday.TUESDAY,
    date(2026, 9, 16): BusinessWeekday.WEDNESDAY,
    date(2026, 9, 17): BusinessWeekday.THURSDAY,
    date(2026, 9, 18): BusinessWeekday.FRIDAY,
    date(2026, 9, 19): BusinessWeekday.SATURDAY,
    date(2026, 9, 20): BusinessWeekday.SUNDAY,
}


def _weekly(
    *, closed: set[BusinessWeekday] | None = None
) -> tuple[WeekdayBusinessHours, ...]:
    """日曜だけ定休の標準的な週次予定を組み立てる。"""
    rest = closed if closed is not None else {BusinessWeekday.SUNDAY}
    return tuple(
        WeekdayBusinessHours(
            weekday=day, slots=() if day in rest else (_MORNING, _AFTERNOON)
        )
        for day in BusinessWeekday
    )


def _hours(**kwargs: object) -> BusinessHours:
    return BusinessHours(weekly=_weekly(), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(("target", "expected"), sorted(_WEEKDAY_SAMPLES.items()))
def test_曜日の対応が実在する日付と一致する(
    target: date, expected: BusinessWeekday
) -> None:
    """曜日番号の対応を列挙の並び順から導かせない。

    並べ替えた瞬間に全店舗の開局判定が1日ずれるので、実在する日付で固定する。
    """
    assert weekday_of(target) == expected


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        (time(8, 59), False),
        (time(9, 0), True),
        (time(12, 59), True),
        (time(13, 0), False),
        (time(14, 0), True),
        (time(18, 59), True),
        (time(19, 0), False),
    ],
)
def test_時間帯は終了時刻を含まない(at: time, expected: bool) -> None:
    """時刻は半開区間で持つ。

    昼休みを挟む 9:00-13:00 と 14:00-19:00 を閉区間にすると、13:00 と 14:00 が
    2つの時間帯にまたがり、同じ時刻が開いているとも閉じているとも言える。
    """
    assert _hours().is_open_at(on=_THURSDAY, at=at) is expected


def test_定休日はどの時刻でも開かない() -> None:
    assert _hours().is_open_at(on=_SUNDAY, at=time(12, 0)) is False


@pytest.mark.parametrize("at", [time(0, 0), time(12, 0), time(23, 59, 59)])
def test_終了時刻の0時はその日の24時を指す(at: time) -> None:
    """``time`` は24時を表せないので、終端の 00:00 だけを24時と読む。"""
    # Arrange
    whole_day = BusinessHourSlot(opens_at=time(0, 0), closes_at=time(0, 0))
    hours = BusinessHours(
        weekly=tuple(
            WeekdayBusinessHours(weekday=day, slots=(whole_day,))
            for day in BusinessWeekday
        )
    )

    # Act & Assert
    assert hours.is_open_at(on=_THURSDAY, at=at) is True


def test_夜間帯は日をまたがず2件に分けて表す() -> None:
    """22時から翌2時までを、その日の22-24時と翌日の0-2時として持つ。"""
    # Arrange
    night = BusinessHourSlot(opens_at=time(22, 0), closes_at=time(0, 0))
    dawn = BusinessHourSlot(opens_at=time(0, 0), closes_at=time(2, 0))
    hours = BusinessHours(
        weekly=tuple(
            WeekdayBusinessHours(weekday=day, slots=(dawn, night))
            for day in BusinessWeekday
        )
    )

    # Act & Assert
    assert hours.is_open_at(on=_THURSDAY, at=time(23, 0)) is True
    assert hours.is_open_at(on=_THURSDAY, at=time(1, 0)) is True
    assert hours.is_open_at(on=_THURSDAY, at=time(3, 0)) is False


@pytest.mark.parametrize(
    ("opens_at", "closes_at"),
    [(time(19, 0), time(9, 0)), (time(9, 0), time(9, 0))],
    ids=["終了が開始より前", "開始と終了が同じ"],
)
def test_終了が開始より後でない時間帯は拒否される(
    opens_at: time, closes_at: time
) -> None:
    with pytest.raises(DomainValidationError, match="終了時刻は開始時刻より後"):
        BusinessHourSlot(opens_at=opens_at, closes_at=closes_at)


def test_タイムゾーン付きの時刻は拒否される() -> None:
    """判定は業務のタイムゾーンで行うので、時刻に帯を持たせない。"""
    with pytest.raises(DomainValidationError, match="タイムゾーンは指定できません"):
        BusinessHourSlot(opens_at=time(9, 0, tzinfo=UTC), closes_at=time(19, 0))


def test_同じ曜日で重なる時間帯は拒否される() -> None:
    with pytest.raises(DomainValidationError, match="開局時間帯が重なっています"):
        WeekdayBusinessHours(
            weekday=BusinessWeekday.MONDAY,
            slots=(
                _MORNING,
                BusinessHourSlot(opens_at=time(12, 0), closes_at=time(18, 0)),
            ),
        )


def test_曜日を1つでも書き忘れると拒否される() -> None:
    """宣言の無い曜日を定休日に倒さない。

    既定を「休み」にすると、書き漏らした店舗が登録できたうえで、その曜日だけ
    静かに閉まる。
    """
    partial = tuple(
        item for item in _weekly() if item.weekday != BusinessWeekday.MONDAY
    )
    with pytest.raises(DomainValidationError, match="全ての曜日"):
        BusinessHours(weekly=partial)


def test_全曜日が定休の予定は拒否される() -> None:
    """営業していないことは店舗の状態が表すので、二通りの表し方を作らない。"""
    with pytest.raises(DomainValidationError, match="少なくとも1日"):
        BusinessHours(weekly=_weekly(closed=set(BusinessWeekday)))


def test_同じ曜日の予定が重複すると拒否される() -> None:
    duplicated = (*_weekly(), WeekdayBusinessHours(weekday=BusinessWeekday.MONDAY))
    with pytest.raises(DomainValidationError, match="同じ曜日"):
        BusinessHours(weekly=duplicated)


def test_臨時休業は週次の予定を上書きする() -> None:
    # Arrange
    hours = _hours(
        exceptions=(
            BusinessDayException(on=_THURSDAY, note=BusinessHoursNote("臨時休業")),
        )
    )

    # Act & Assert
    assert hours.is_open_at(on=_THURSDAY, at=time(12, 0)) is False
    assert hours.slots_on(_THURSDAY) == ()


def test_臨時開局は定休日を上書きする() -> None:
    """祝日や年末年始はここへ登録する運用にする。"""
    # Arrange
    hours = _hours(
        exceptions=(
            BusinessDayException(
                on=_SUNDAY, slots=(_MORNING,), note=BusinessHoursNote("休日当番")
            ),
        )
    )

    # Act & Assert
    assert hours.is_open_at(on=_SUNDAY, at=time(10, 0)) is True
    assert hours.is_open_at(on=_SUNDAY, at=time(15, 0)) is False


def test_同じ日付の特例が重複すると拒否される() -> None:
    with pytest.raises(DomainValidationError, match="同じ日付の特例"):
        _hours(
            exceptions=(
                BusinessDayException(on=_THURSDAY),
                BusinessDayException(on=_THURSDAY, slots=(_MORNING,)),
            )
        )


def test_開局時間が未登録の店舗は判定できないと答える() -> None:
    """「登録が無いから開いている」に倒さない。

    案内や電話対応が実在しない時刻を伝えるより、判定できないと答えるほうが安全。
    """
    store = create_store()
    assert store.business_hours is None
    assert (
        store.opening_state_at(on=_THURSDAY, at=time(12, 0))
        == StoreOpeningState.UNKNOWN
    )


@pytest.mark.parametrize("status", [StoreStatus.SUSPENDED, StoreStatus.CLOSED])
def test_有効でない店舗は時間表に関わらず閉まっている(status: StoreStatus) -> None:
    """休止中の薬局へ患者を案内させない。"""
    store = replace(create_store(), status=status, business_hours=_hours())
    assert (
        store.opening_state_at(on=_THURSDAY, at=time(12, 0)) == StoreOpeningState.CLOSED
    )


@pytest.mark.parametrize(
    ("at", "expected"),
    [(time(12, 0), StoreOpeningState.OPEN), (time(20, 0), StoreOpeningState.CLOSED)],
)
def test_有効な店舗は時間表どおりに開閉する(
    at: time, expected: StoreOpeningState
) -> None:
    store = create_store().change_business_hours(_hours())
    assert store.opening_state_at(on=_THURSDAY, at=at) == expected
