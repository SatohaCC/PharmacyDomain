"""管理薬剤師の在任期間と、他店舗への勤務期間の重なりを検証する。"""

from datetime import date

import pytest

from app.domain.staff.identifiers import StaffId
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.identifiers import StoreId
from app.domain.store.services import StoreManagerAssignmentService
from app.domain.store.value_objects import ManagerStaffAffiliation, ManagerStaffSource
from tests.factories.store_factory import create_manager_assignment, create_store


@pytest.mark.parametrize(
    "starts_on,ends_on,conflict",
    [
        (date(2026, 9, 1), date(2026, 9, 30), False),
        (date(2026, 9, 1), date(2026, 10, 1), True),
        (date(2026, 10, 31), date(2026, 11, 30), True),
        (date(2026, 11, 1), None, False),
        (date(2026, 1, 1), None, True),
    ],
)
def test_管理薬剤師_在任期間中の他店舗勤務だけを_終了日を含めて拒否する(
    starts_on: date,
    ends_on: date | None,
    conflict: bool,
) -> None:
    # Arrange
    store = create_store()
    staff = StaffId.generate()
    assignment = create_manager_assignment(
        corporate_id=store.corporate_id,
        store_id=store.id,
        staff_id=staff,
        starts_on=date(2026, 10, 1),
        ends_on=date(2026, 10, 31),
    )
    source = ManagerStaffSource(
        staff_id=staff,
        corporate_id=store.corporate_id,
        staff_is_active=True,
        has_pharmacist=True,
        affiliations=(
            ManagerStaffAffiliation(
                store_id=store.id, starts_on=date(2026, 1, 1), ends_on=None
            ),
            ManagerStaffAffiliation(
                store_id=StoreId.generate(), starts_on=starts_on, ends_on=ends_on
            ),
        ),
    )
    # Act / Assert
    if conflict:
        with pytest.raises(ManagerAssignmentConflictError):
            StoreManagerAssignmentService().ensure_assignable(
                assignment, store=store, staff=source
            )
    else:
        StoreManagerAssignmentService().ensure_assignable(
            assignment, store=store, staff=source
        )
