"""開局時間の登録と、業務のタイムゾーンで行う開局判定。"""

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, timezone

import pytest

from app.application.store.business_hours import (
    BusinessDayExceptionInput,
    BusinessHourSlotInput,
    ChangeStoreBusinessHoursCommand,
    ChangeStoreBusinessHoursUseCase,
    GetStoreOpeningStatusUseCase,
    StoreOpeningStatusQuery,
    WeekdayBusinessHoursInput,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.business_hours import BusinessWeekday, StoreOpeningState
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.store import Store
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

#: 2026-09-17 は木曜。JSTの正午はUTCでは同日3時。
_JST_NOON_IN_UTC = datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
_THURSDAY = date(2026, 9, 17)

_SLOTS = (
    BusinessHourSlotInput(opens_at=time(9, 0), closes_at=time(13, 0)),
    BusinessHourSlotInput(opens_at=time(14, 0), closes_at=time(19, 0)),
)


def _weekly() -> tuple[WeekdayBusinessHoursInput, ...]:
    """日曜だけ定休の週次予定。"""
    return tuple(
        WeekdayBusinessHoursInput(
            weekday=day,
            slots=() if day == BusinessWeekday.SUNDAY else _SLOTS,
        )
        for day in BusinessWeekday
    )


async def _registered(
    store: Store,
    *,
    exceptions: tuple[BusinessDayExceptionInput, ...] = (),
) -> InMemoryStoreRepository:
    """開局時間を登録した店舗を持つRepositoryを返す。"""
    stores = InMemoryStoreRepository()
    await stores.save(store)
    await ChangeStoreBusinessHoursUseCase(
        stores, create_vendor_corporate_access()
    ).execute(
        ChangeStoreBusinessHoursCommand(
            corporate_id=str(store.corporate_id.value),
            store_id=str(store.id.value),
            weekly=_weekly(),
            exceptions=exceptions,
        )
    )
    return stores


def _status_use_case(
    stores: InMemoryStoreRepository, now: datetime
) -> GetStoreOpeningStatusUseCase:
    return GetStoreOpeningStatusUseCase(
        stores, create_vendor_corporate_access(), FakeClock(now)
    )


def _query(store: Store, at: datetime | None = None) -> StoreOpeningStatusQuery:
    return StoreOpeningStatusQuery(
        corporate_id=str(store.corporate_id.value),
        store_id=str(store.id.value),
        at=at,
    )


@pytest.mark.asyncio
async def test_登録した開局時間が店舗に残る() -> None:
    # Arrange
    store = create_store()

    # Act
    stores = await _registered(store)

    # Assert
    saved = await stores.get(store.id)
    assert saved is not None and saved.business_hours is not None
    assert len(saved.business_hours.weekly) == len(BusinessWeekday)


@pytest.mark.asyncio
async def test_開局時間の照会は注入した時計の業務時刻で判定する() -> None:
    """UTCの3時はJSTの正午。時計をそのまま使うと昼と朝を取り違える。"""
    # Arrange
    store = create_store()
    stores = await _registered(store)

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store))

    # Assert
    assert actual.state == StoreOpeningState.OPEN.value
    assert actual.on == _THURSDAY
    assert actual.at == time(12, 0)


@pytest.mark.asyncio
async def test_業務日は日本時間で決まる() -> None:
    """UTCの23時は翌日のJST8時。日付の側もずらす。"""
    # Arrange
    store = create_store()
    stores = await _registered(store)

    # Act
    actual = await _status_use_case(
        stores, datetime(2026, 9, 17, 23, 0, tzinfo=UTC)
    ).execute(_query(store))

    # Assert
    assert actual.on == date(2026, 9, 18)
    assert actual.at == time(8, 0)
    assert actual.state == StoreOpeningState.CLOSED.value


@pytest.mark.asyncio
async def test_別のタイムゾーンで指定した日時も業務時刻へ揃える() -> None:
    """呼び出し側の帯をそのまま使わない。"""
    # Arrange
    store = create_store()
    stores = await _registered(store)
    # ハワイ時間（UTC-10）の 2026-09-16 07:00 は、日本時間では同年9月17日の2時。
    hawaii = timezone(timedelta(hours=-10))
    hawaii_moment = datetime(2026, 9, 16, 7, 0, tzinfo=hawaii)

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(
        _query(store, hawaii_moment)
    )

    # Assert
    assert actual.on == _THURSDAY
    assert actual.at == time(2, 0)


@pytest.mark.asyncio
async def test_タイムゾーンの無い日時は拒否される() -> None:
    """UTCのつもりとJSTのつもりが同じ形で届き、9時間ずれた答えを返してしまう。"""
    # Arrange
    store = create_store()
    stores = await _registered(store)
    naive = datetime(2026, 9, 17, 12, 0)  # noqa: DTZ001

    # Act & Assert
    with pytest.raises(DomainValidationError, match="タイムゾーンが必要"):
        await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store, naive))


@pytest.mark.asyncio
async def test_開局時間が未登録なら判定できないと返す() -> None:
    """未登録を「開いている」にも「閉じている」にも倒さない。"""
    # Arrange
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store))

    # Assert
    assert actual.state == StoreOpeningState.UNKNOWN.value
    assert actual.slots == ()


@pytest.mark.asyncio
async def test_臨時休業の日は閉まっていて時間帯も返らない() -> None:
    # Arrange
    store = create_store()
    stores = await _registered(
        store,
        exceptions=(BusinessDayExceptionInput(on=_THURSDAY, note="臨時休業"),),
    )

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store))

    # Assert
    assert actual.state == StoreOpeningState.CLOSED.value
    assert actual.slots == ()


@pytest.mark.asyncio
async def test_開局している日はその日の時間帯を返す() -> None:
    """「今日は何時まで開いているか」を1回の照会で答えられるようにする。"""
    # Arrange
    store = create_store()
    stores = await _registered(store)

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store))

    # Assert
    assert [(item.opens_at, item.closes_at) for item in actual.slots] == [
        (time(9, 0), time(13, 0)),
        (time(14, 0), time(19, 0)),
    ]


@pytest.mark.asyncio
async def test_休止中の店舗は開局時間に関わらず閉まっている() -> None:
    # Arrange
    store = create_store()
    stores = await _registered(store)
    saved = await stores.get(store.id)
    assert saved is not None
    await stores.save(replace(saved, status=StoreStatus.SUSPENDED))

    # Act
    actual = await _status_use_case(stores, _JST_NOON_IN_UTC).execute(_query(store))

    # Assert
    assert actual.state == StoreOpeningState.CLOSED.value


@pytest.mark.asyncio
async def test_特例日の理由は空文字を解除として扱う() -> None:
    """任意項目の空文字はApplication境界で ``None`` へ正規化する。"""
    # Arrange
    store = create_store()

    # Act
    stores = await _registered(
        store, exceptions=(BusinessDayExceptionInput(on=_THURSDAY, note="   "),)
    )

    # Assert
    saved = await stores.get(store.id)
    assert saved is not None and saved.business_hours is not None
    assert saved.business_hours.exceptions[0].note is None
