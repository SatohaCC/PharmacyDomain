"""InMemoryStaffRepository および StaffRepository の法人境界動作テスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.corporate import CorporateId
from app.domain.staff import StaffCode, StaffCodeAlreadyExistsError, StaffId
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_get_returns_staff_when_corporate_id_matches() -> None:
    # Arrange
    repo = InMemoryStaffRepository()
    corp_id = CorporateId.generate()
    staff = create_staff(corporate_id=corp_id, code="STF-001")
    await repo.save(staff)

    # Act
    actual = await repo.get(corporate_id=corp_id, staff_id=staff.id)

    # Assert
    assert actual is not None
    assert actual.id == staff.id
    assert actual.corporate_id == corp_id


@pytest.mark.asyncio
async def test_get_returns_none_when_corporate_id_does_not_match() -> None:
    # Arrange: 法人Aに属するスタッフを作成して保存
    repo = InMemoryStaffRepository()
    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()
    staff_a = create_staff(corporate_id=corp_a_id, code="STF-001")
    await repo.save(staff_a)

    # Act: 法人BのIDで検索を試みる
    actual = await repo.get(corporate_id=corp_b_id, staff_id=staff_a.id)

    # Assert: 他法人のデータのアクセスは境界保護により None になること
    assert actual is None


@pytest.mark.asyncio
async def test_get_returns_none_when_staff_id_not_found() -> None:
    # Arrange
    repo = InMemoryStaffRepository()
    corp_id = CorporateId.generate()
    dummy_staff_id = StaffId.generate()

    # Act
    actual = await repo.get(corporate_id=corp_id, staff_id=dummy_staff_id)

    # Assert
    assert actual is None


@pytest.mark.asyncio
async def test_save_rejects_duplicate_staff_code_in_same_corporate() -> None:
    # Arrange
    repo = InMemoryStaffRepository()
    corp_id = CorporateId.generate()
    staff1 = create_staff(corporate_id=corp_id, code="STF-001")
    staff2 = create_staff(corporate_id=corp_id, code="STF-001")

    await repo.save(staff1)

    # Act / Assert
    with pytest.raises(StaffCodeAlreadyExistsError):
        await repo.save(staff2)


@pytest.mark.asyncio
async def test_save_allows_same_staff_code_in_different_corporates() -> None:
    # Arrange
    repo = InMemoryStaffRepository()
    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()

    staff_a = create_staff(corporate_id=corp_a_id, code="STF-001")
    staff_b = create_staff(corporate_id=corp_b_id, code="STF-001")

    # Act
    await repo.save(staff_a)
    await repo.save(staff_b)

    # Assert: 別法人であれば同じスタッフコードでも登録できる
    retrieved_a = await repo.get(corporate_id=corp_a_id, staff_id=staff_a.id)
    retrieved_b = await repo.get(corporate_id=corp_b_id, staff_id=staff_b.id)
    assert retrieved_a is not None
    assert retrieved_b is not None


@pytest.mark.asyncio
async def test_list_by_corporate_id_returns_only_staffs_of_given_corporate() -> None:
    # Arrange
    repo = InMemoryStaffRepository()
    corp_a_id = CorporateId.generate()
    corp_b_id = CorporateId.generate()

    staff_a1 = create_staff(corporate_id=corp_a_id, code="STF-001")
    staff_a2 = create_staff(corporate_id=corp_a_id, code="STF-002")
    staff_b1 = create_staff(corporate_id=corp_b_id, code="STF-001")

    await repo.save(staff_a1)
    await repo.save(staff_a2)
    await repo.save(staff_b1)

    # Act
    actual = await repo.list_by_corporate_id(corp_a_id)

    # Assert
    assert len(actual) == 2
    assert {s.id for s in actual} == {staff_a1.id, staff_a2.id}


@pytest.mark.asyncio
async def test_スタッフコード_無効化済みスタッフのコードも_重複として拒否される() -> (
    None
):
    """``ACTIVE_FLAG_KEY_REUSE["Staff"] is False`` の実挙動を固定する。

    外部患者ID（再利用可）と逆の判断であり、過去の調剤録・監査の追跡を
    壊さないためにスタッフコードは無効化後も解放しない。
    """
    # Arrange
    repo = InMemoryStaffRepository()
    corp_id = CorporateId.generate()
    retired = create_staff(corporate_id=corp_id, code="STF-001")
    await repo.save(retired)
    await repo.save(retired.deactivate(date(2026, 3, 31)))

    # Act
    actual = await repo.exists_by_code(corporate_id=corp_id, code=StaffCode("STF-001"))

    # Assert
    assert actual is True
