"""スタッフ氏名変更ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.staff import ChangeStaffNamesCommand, ChangeStaffNamesUseCase
from app.domain.corporate import CorporateId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
async def test_change_staff_names_success() -> None:
    # Arrange
    staff_repo = InMemoryStaffRepository()
    use_case = ChangeStaffNamesUseCase(
        repository=staff_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    corp_id = CorporateId.generate()
    staff = create_staff(
        corporate_id=corp_id,
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
    )
    await staff_repo.save(staff)

    cmd = ChangeStaffNamesCommand(
        corporate_id=str(corp_id.value),
        staff_id=str(staff.id.value),
        last_name="鈴木",
        first_name="花子",
        last_name_kana="スズキ",
        first_name_kana="ハナコ",
    )

    # Act
    await use_case.execute(cmd)

    # Assert
    updated_staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff.id)
    assert updated_staff is not None
    assert updated_staff.names.kanji.last_name.value == "鈴木"
    assert updated_staff.names.kanji.first_name.value == "花子"
    assert updated_staff.names.kana.last_name.value == "スズキ"
    assert updated_staff.names.kana.first_name.value == "ハナコ"
