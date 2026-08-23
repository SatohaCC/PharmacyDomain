"""スタッフドメインサービスのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.corporate import CorporateId
from app.domain.staff import (
    AffiliationDateConflictError,
    ConcurrentStoreConflictError,
    InvalidCorporateAssignmentError,
    StaffCode,
    StaffCodeAlreadyExistsError,
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_ensure_code_is_unique_raises_error_when_code_exists() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    service = StaffCodeUniquenessService(staff_repo)
    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id, code="STF-001")
    await staff_repo.save(staff)

    # Act / Assert
    with pytest.raises(StaffCodeAlreadyExistsError):
        await service.ensure_code_is_unique(
            corporate_id=corp_id,
            code=StaffCode("STF-001"),
        )


def test_assign_home_store_raises_error_when_store_belongs_to_different_corporate() -> (
    None
):
    # Arrange
    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()

    store_b = create_store(corporate_id=corp_b_id, name="他法人店舗")
    assignment_service = StaffStoreAssignmentService()
    staff_a = create_staff(corporate_id=corp_a_id, code="STF-001")

    # Act / Assert: 別法人店舗への配属は InvalidCorporateAssignmentError となること
    with pytest.raises(InvalidCorporateAssignmentError):
        assignment_service.assign_home_store(
            staff=staff_a,
            store=store_b,
            start_date=date(2026, 4, 1),
        )


def test_assign_home_store_succeeds_when_store_belongs_to_same_corporate() -> None:
    # Arrange
    corp_id = CorporateId.generate()

    store = create_store(corporate_id=corp_id, name="自法人店舗")
    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id, code="STF-001")

    today = date(2026, 4, 1)

    # Act
    updated_staff = assignment_service.assign_home_store(
        staff=staff,
        store=store,
        start_date=today,
    )

    # Assert
    assert updated_staff.current_home_store_id(today) == store.id


def test_remove_concurrent_store_raises_error_when_no_active_affiliation_found() -> (
    None
):
    # Arrange
    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id, name="兼務店舗")
    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id)

    # Act / Assert: 有効な兼務履歴が存在しない場合に ConcurrentStoreConflictError となること
    with pytest.raises(ConcurrentStoreConflictError):
        assignment_service.remove_concurrent_store(
            staff=staff,
            store=store,
            end_date=date(2026, 4, 1),
        )


def test_transfer_home_store_raises_error_when_future_primary_affiliation_exists() -> (
    None
):
    # Arrange
    corp_id = CorporateId.generate()
    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    store_c = create_store(corporate_id=corp_id, name="店舗C")

    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id)

    # 店舗A配属 (2026-04-01)
    staff = assignment_service.assign_home_store(staff, store_a, date(2026, 4, 1))

    # 未来の店舗B異動予約 (2026-06-01)
    staff = assignment_service.transfer_home_store(staff, store_b, date(2026, 6, 1))

    # Act / Assert: 未来の予約（2026-06-01）より過去/中間（2026-05-01）への割り込み異動は AffiliationDateConflictError となること
    with pytest.raises(AffiliationDateConflictError):
        assignment_service.transfer_home_store(staff, store_c, date(2026, 5, 1))


def test_兼務追加_過去に遡って既存兼務と重なる期間を指定すると_兼務衝突エラーになる() -> (
    None
):
    # Arrange
    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id, name="店舗A")
    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id)
    staff = assignment_service.assign_concurrent_store(staff, store, date(2026, 3, 1))
    staff = assignment_service.remove_concurrent_store(staff, store, date(2026, 6, 30))

    # Act / Assert: 開始日時点しか見ない事前判定では素通りしていた過去への遡り
    with pytest.raises(ConcurrentStoreConflictError):
        assignment_service.assign_concurrent_store(staff, store, date(2026, 1, 1))


def test_主所属異動_異動先が兼務中の店舗だと_兼務衝突エラーになる() -> None:
    # Arrange
    corp_id = CorporateId.generate()
    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id)
    staff = assignment_service.assign_home_store(staff, store_a, date(2026, 4, 1))
    staff = assignment_service.assign_concurrent_store(staff, store_b, date(2026, 4, 1))

    # Act / Assert: 主所属と兼務が同一店舗で同居する矛盾を作らせない
    with pytest.raises(ConcurrentStoreConflictError):
        assignment_service.transfer_home_store(staff, store_b, date(2026, 7, 1))


def test_主所属異動_兼務を解除してから異動すると_主所属が切り替わる() -> None:
    # Arrange
    corp_id = CorporateId.generate()
    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    assignment_service = StaffStoreAssignmentService()
    staff = create_staff(corporate_id=corp_id)
    staff = assignment_service.assign_home_store(staff, store_a, date(2026, 4, 1))
    staff = assignment_service.assign_concurrent_store(staff, store_b, date(2026, 4, 1))

    # Act
    staff = assignment_service.remove_concurrent_store(
        staff, store_b, date(2026, 6, 30)
    )
    staff = assignment_service.transfer_home_store(staff, store_b, date(2026, 7, 1))

    # Assert
    assert staff.current_home_store_id(date(2026, 7, 1)) == store_b.id
    assert staff.current_concurrent_store_ids(date(2026, 7, 1)) == frozenset()
