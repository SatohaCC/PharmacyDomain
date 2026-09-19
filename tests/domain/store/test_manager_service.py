"""管理薬剤師の資格と所属の整合性。"""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.foundation.exceptions import DomainError
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_service import StoreManagerAssignmentService
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store


@pytest.mark.parametrize("primary", [True, False])
@pytest.mark.parametrize("state", [StoreStatus.ACTIVE, StoreStatus.SUSPENDED])
def test_任命期間を含む所属の薬剤師を任命できる(
    primary: bool, state: StoreStatus
) -> None:
    store = replace(create_store(), status=state)
    staff = replace(
        create_staff(corporate_id=store.corporate_id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("654321"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=primary,
                period=AffiliationPeriod(
                    start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)
                ),
            ),
        ),
    )
    assignment = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=store.corporate_id,
        store_id=store.id,
        staff_id=staff.id,
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 10, 1), ends_on=date(2026, 10, 31)
        ),
    )

    StoreManagerAssignmentService().ensure_assignable(
        assignment, store=store, staff=staff
    )


@pytest.mark.parametrize(
    "violation",
    [
        "資格なし",
        "退職済み",
        "所属なし",
        "開始前",
        "終了後",
        "無期限",
        "閉局",
        "別法人",
    ],
)
def test_資格や所属期間を満たさない任命を拒否する(violation: str) -> None:
    store = create_store()
    staff = replace(
        create_staff(corporate_id=store.corporate_id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("654321"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=True,
                period=AffiliationPeriod(
                    start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)
                ),
            ),
        ),
    )
    start, end = date(2026, 10, 1), date(2026, 10, 31)
    if violation == "資格なし":
        staff = replace(staff, qualifications=StaffQualifications.empty())
    elif violation == "退職済み":
        staff = staff.deactivate(date(2026, 10, 31))
    elif violation == "所属なし":
        staff = replace(staff, affiliations=())
    elif violation == "開始前":
        start = date(2026, 9, 30)
    elif violation == "終了後":
        end = date(2026, 11, 1)
    elif violation == "閉局":
        store = replace(store, status=StoreStatus.CLOSED)
    elif violation == "別法人":
        staff = replace(staff, corporate_id=create_store().corporate_id)
    assignment = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=store.corporate_id,
        store_id=store.id,
        staff_id=staff.id,
        period=ManagerAssignmentPeriod(
            starts_on=start, ends_on=None if violation == "無期限" else end
        ),
    )

    with pytest.raises(DomainError):
        StoreManagerAssignmentService().ensure_assignable(
            assignment, store=store, staff=staff
        )
