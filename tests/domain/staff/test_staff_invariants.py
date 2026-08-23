"""Staff集約の所属履歴に関する不変条件テスト。

``Staff`` は frozen dataclass なのでインスタンスを得る経路は ``__init__`` しかなく、
``Entity.__post_init__`` が必ず ``validate()`` を呼ぶ。したがって
``create()`` / ``dataclasses.replace()`` / Repositoryからの復元 / テストの直接構築の
すべてがここで固定する不変条件を通る。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.domain.corporate import CorporateId
from app.domain.staff import (
    AffiliationPeriod,
    ConcurrentStoreConflictError,
    PrimaryAffiliationDuplicationError,
    Staff,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreId
from tests.factories.staff_factory import create_staff


def _create_affiliation(
    *,
    store_id: StoreId,
    start_date: date,
    end_date: date | None = None,
    is_primary: bool,
) -> StoreAffiliation:
    """テスト用の所属履歴1行を生成する。"""
    return StoreAffiliation(
        store_id=store_id,
        period=AffiliationPeriod(start_date=start_date, end_date=end_date),
        is_primary=is_primary,
    )


def _create_staff_with_affiliations(*affiliations: StoreAffiliation) -> Staff:
    """所属履歴を直接持たせた Staff を生成する。"""
    return replace(
        create_staff(corporate_id=CorporateId.generate()),
        affiliations=affiliations,
    )


def test_スタッフ_同日に有効な主所属を2店舗分持たせると_主所属重複エラーになる() -> (
    None
):
    # Arrange
    store_a, store_b = StoreId.generate(), StoreId.generate()
    affiliations = (
        _create_affiliation(
            store_id=store_a, start_date=date(2026, 1, 1), is_primary=True
        ),
        _create_affiliation(
            store_id=store_b, start_date=date(2026, 1, 1), is_primary=True
        ),
    )

    # Act / Assert
    with pytest.raises(PrimaryAffiliationDuplicationError):
        _create_staff_with_affiliations(*affiliations)


def test_スタッフ_日付を跨いで重なる主所属を持たせると_主所属重複エラーになる() -> None:
    # Arrange
    store_a, store_b = StoreId.generate(), StoreId.generate()
    affiliations = (
        _create_affiliation(
            store_id=store_a,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_primary=True,
        ),
        _create_affiliation(
            store_id=store_b, start_date=date(2026, 6, 30), is_primary=True
        ),
    )

    # Act / Assert
    with pytest.raises(PrimaryAffiliationDuplicationError):
        _create_staff_with_affiliations(*affiliations)


def test_スタッフ_同一店舗を主所属と兼務で同時に持たせると_兼務衝突エラーになる() -> (
    None
):
    # Arrange
    store_id = StoreId.generate()
    affiliations = (
        _create_affiliation(
            store_id=store_id, start_date=date(2026, 4, 1), is_primary=False
        ),
        _create_affiliation(
            store_id=store_id, start_date=date(2026, 7, 1), is_primary=True
        ),
    )

    # Act / Assert
    with pytest.raises(ConcurrentStoreConflictError):
        _create_staff_with_affiliations(*affiliations)


def test_スタッフ_同一店舗の兼務期間が重なると_兼務衝突エラーになる() -> None:
    # Arrange
    store_id = StoreId.generate()
    affiliations = (
        _create_affiliation(
            store_id=store_id,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            is_primary=False,
        ),
        _create_affiliation(
            store_id=store_id, start_date=date(2026, 1, 1), is_primary=False
        ),
    )

    # Act / Assert
    with pytest.raises(ConcurrentStoreConflictError):
        _create_staff_with_affiliations(*affiliations)


def test_スタッフ_期間が重ならない主所属履歴と別店舗の兼務なら_生成できる() -> None:
    # Arrange
    store_a, store_b, store_c = (
        StoreId.generate(),
        StoreId.generate(),
        StoreId.generate(),
    )
    affiliations = (
        _create_affiliation(
            store_id=store_a,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_primary=True,
        ),
        _create_affiliation(
            store_id=store_b, start_date=date(2026, 7, 1), is_primary=True
        ),
        _create_affiliation(
            store_id=store_c, start_date=date(2026, 2, 1), is_primary=False
        ),
    )

    # Act
    actual = _create_staff_with_affiliations(*affiliations)

    # Assert
    assert actual.current_home_store_id(date(2026, 3, 1)) == store_a
    assert actual.current_home_store_id(date(2026, 8, 1)) == store_b
    assert actual.current_concurrent_store_ids(date(2026, 8, 1)) == frozenset({store_c})


def test_スタッフ_同一店舗でも期間が隣接していれば_生成できる() -> None:
    # Arrange
    store_id = StoreId.generate()
    affiliations = (
        _create_affiliation(
            store_id=store_id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_primary=False,
        ),
        _create_affiliation(
            store_id=store_id, start_date=date(2026, 7, 1), is_primary=True
        ),
    )

    # Act
    actual = _create_staff_with_affiliations(*affiliations)

    # Assert
    assert actual.current_home_store_id(date(2026, 7, 1)) == store_id
    assert actual.current_concurrent_store_ids(date(2026, 7, 1)) == frozenset()


def test_スタッフ_不正な所属履歴でreplaceすると_ドメインエラーになる() -> None:
    # Arrange
    staff = create_staff()
    store_id = StoreId.generate()
    overlapping = (
        _create_affiliation(
            store_id=store_id, start_date=date(2026, 1, 1), is_primary=True
        ),
        _create_affiliation(
            store_id=StoreId.generate(), start_date=date(2026, 5, 1), is_primary=True
        ),
    )

    # Act / Assert
    with pytest.raises(PrimaryAffiliationDuplicationError):
        replace(staff, affiliations=overlapping)


def test_現在主所属店舗_有効な主所属が無い日を指定すると_Noneを返す() -> None:
    # Arrange
    staff = _create_staff_with_affiliations(
        _create_affiliation(
            store_id=StoreId.generate(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_primary=True,
        )
    )

    # Act
    actual = staff.current_home_store_id(date(2026, 7, 1))

    # Assert
    assert actual is None
