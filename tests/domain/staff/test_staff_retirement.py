"""スタッフの無効化（退職）と店舗所属履歴の連動テスト。

``is_active`` は日付を持たない現在フラグだが、``current_home_store_id()`` は
適用日ごとの導出である。フラグだけを倒すと所属が無期限のまま残り、退職後の
日付でも所属店舗が返る。逆に導出側でフラグを見て打ち切ると、在籍していた
過去日の所属まで引けなくなり調剤録・監査の追跡が切れる。ここでは退職日を
所属履歴（もともと日付つき）へ書き込むことで両方を満たすことを固定する。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.domain.corporate import CorporateId
from app.domain.staff import (
    AffiliationDateConflictError,
    AffiliationPeriod,
    InactiveStaffAssignmentError,
    Staff,
    StaffStoreAssignmentService,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreId
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store

RETIRED_ON = date(2026, 3, 31)


def _affiliation(
    *,
    store_id: StoreId,
    start_date: date,
    end_date: date | None = None,
    is_primary: bool = True,
) -> StoreAffiliation:
    """テスト用の所属履歴1行を生成する。"""
    return StoreAffiliation(
        store_id=store_id,
        period=AffiliationPeriod(start_date=start_date, end_date=end_date),
        is_primary=is_primary,
    )


def _staff_with(*affiliations: StoreAffiliation) -> Staff:
    """所属履歴を直接持たせた Staff を生成する。"""
    return replace(
        create_staff(corporate_id=CorporateId.generate()),
        affiliations=affiliations,
    )


def test_スタッフ_無効化すると_継続中の主所属が退職日で終了する() -> None:
    # Arrange
    store_id = StoreId.generate()
    staff = _staff_with(_affiliation(store_id=store_id, start_date=date(2026, 1, 1)))

    # Act
    actual = staff.deactivate(RETIRED_ON)

    # Assert
    assert actual.is_active is False
    assert actual.affiliations[0].period.end_date == RETIRED_ON


def test_スタッフ_無効化しても_在籍していた過去日の主所属は引ける() -> None:
    """導出を ``is_active`` で打ち切らないことの固定。

    退職の瞬間に過去日の所属が引けなくなると、そのスタッフが関わった調剤録の
    追跡が切れる。スタッフコードを無効化後も解放しない判断と同じ理由で、
    過去日の問い合わせは退職後も答えられなければならない。
    """
    # Arrange
    store_id = StoreId.generate()
    staff = _staff_with(_affiliation(store_id=store_id, start_date=date(2026, 1, 1)))

    # Act
    actual = staff.deactivate(RETIRED_ON)

    # Assert
    assert actual.current_home_store_id(date(2026, 2, 1)) == store_id
    assert actual.current_home_store_id(RETIRED_ON) == store_id
    assert actual.current_home_store_id(date(2026, 4, 1)) is None


def test_スタッフ_無効化すると_退職日より後まで続く兼務も退職日で打ち切られる() -> None:
    # Arrange
    concurrent_store_id = StoreId.generate()
    staff = _staff_with(
        _affiliation(
            store_id=concurrent_store_id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_primary=False,
        )
    )

    # Act
    actual = staff.deactivate(RETIRED_ON)

    # Assert
    assert actual.affiliations[0].period.end_date == RETIRED_ON
    assert actual.current_concurrent_store_ids(date(2026, 4, 1)) == frozenset()


def test_スタッフ_無効化しても_退職日以前に終了済みの所属はそのまま残る() -> None:
    # Arrange
    store_id = StoreId.generate()
    ended_on = date(2026, 1, 31)
    staff = _staff_with(
        _affiliation(store_id=store_id, start_date=date(2026, 1, 1), end_date=ended_on)
    )

    # Act
    actual = staff.deactivate(RETIRED_ON)

    # Assert
    assert actual.affiliations[0].period.end_date == ended_on


def test_スタッフ_退職日より後に開始する所属予約があると_無効化は日付衝突エラーになる() -> (
    None
):
    """未来の配属予約を黙って捨てない。

    退職日で閉じると開始日が終了日を追い越すため、期間として成立しない。
    予約を消すか退職日を後ろへずらすかは業務判断なので、集約は拒否に倒す。
    """
    # Arrange
    staff = _staff_with(
        _affiliation(store_id=StoreId.generate(), start_date=date(2026, 5, 1))
    )

    # Act / Assert
    with pytest.raises(AffiliationDateConflictError):
        staff.deactivate(RETIRED_ON)


def test_スタッフ_有効化しても_退職で閉じた所属は復活しない() -> None:
    """復職後にどの店舗へ戻るかは復職時に決まる事実で、退職前の所属から導出できない。"""
    # Arrange
    store_id = StoreId.generate()
    staff = _staff_with(_affiliation(store_id=store_id, start_date=date(2026, 1, 1)))

    # Act
    actual = staff.deactivate(RETIRED_ON).activate()

    # Assert
    assert actual.is_active is True
    assert actual.affiliations[0].period.end_date == RETIRED_ON
    assert actual.current_home_store_id(date(2026, 4, 1)) is None


def test_スタッフ_無効化済みのスタッフには_主所属を配属できない() -> None:
    """退職者へ無期限の所属を足せると、退職日で閉じた意味が失われる。"""
    # Arrange
    service = StaffStoreAssignmentService()
    corporate_id = CorporateId.generate()
    staff = create_staff(corporate_id=corporate_id).deactivate(RETIRED_ON)
    store = create_store(corporate_id=corporate_id)

    # Act / Assert
    with pytest.raises(InactiveStaffAssignmentError):
        service.assign_home_store(staff, store, date(2026, 4, 1))


def test_スタッフ_無効化済みのスタッフには_兼務を追加できない() -> None:
    # Arrange
    service = StaffStoreAssignmentService()
    corporate_id = CorporateId.generate()
    staff = create_staff(corporate_id=corporate_id).deactivate(RETIRED_ON)
    store = create_store(corporate_id=corporate_id)

    # Act / Assert
    with pytest.raises(InactiveStaffAssignmentError):
        service.assign_concurrent_store(staff, store, date(2026, 4, 1))


def test_スタッフ_無効化済みのスタッフでも_兼務解除はできる() -> None:
    """所属を増やす操作だけを止める。履歴の訂正まで塞ぐと退職後に直せなくなる。"""
    # Arrange
    service = StaffStoreAssignmentService()
    corporate_id = CorporateId.generate()
    store = create_store(corporate_id=corporate_id)
    staff = replace(
        create_staff(corporate_id=corporate_id),
        affiliations=(
            _affiliation(
                store_id=store.id, start_date=date(2026, 1, 1), is_primary=False
            ),
        ),
    ).deactivate(RETIRED_ON)

    # Act
    actual = service.remove_concurrent_store(staff, store, date(2026, 2, 28))

    # Assert
    assert actual.affiliations[0].period.end_date == date(2026, 2, 28)
