"""Staff エンティティおよびドメインモデルの動作テスト。"""

from __future__ import annotations

from datetime import date

from app.base.domain.primitives.primitives import BaseNormalizedString
from app.domain.corporate import CorporateId
from app.domain.staff import (
    InsurancePharmacistRegistration,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StaffStoreAssignmentService,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store


def test_staff_pharmacist_qualification() -> None:
    # Arrange
    license_num = PharmacistLicenseNumber("123456")
    insurance_reg = InsurancePharmacistRegistration(
        registration_number=BaseNormalizedString("REG-123"),
        registration_date=date(2020, 1, 1),
    )
    profile = PharmacistProfile(
        license_number=license_num,
        insurance_registration=insurance_reg,
    )
    qualifications = StaffQualifications.from_profiles(profile)

    # Act
    staff = create_staff(qualifications=qualifications)

    # Assert
    assert staff.is_pharmacist is True
    assert staff.is_dietitian is False
    assert staff.pharmacist_profile is not None
    assert staff.pharmacist_profile.can_bill_insurance() is True


def test_staff_can_access_store_based_on_affiliations() -> None:
    # Arrange
    corp_id = CorporateId.generate()
    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    assignment_service = StaffStoreAssignmentService()

    staff = create_staff(corporate_id=corp_id)

    # Act: store_a に主所属を設定
    staff = assignment_service.assign_home_store(
        staff, store_a, start_date=date(2026, 1, 1)
    )

    # Assert
    assert staff.current_home_store_id(date(2026, 1, 15)) == store_a.id
    assert staff.can_access_store(store_a.id, date(2026, 1, 15)) is True
    assert staff.can_access_store(store_b.id, date(2026, 1, 15)) is False

    # Act: store_b に兼務追加
    staff = assignment_service.assign_concurrent_store(
        staff, store_b, start_date=date(2026, 2, 1)
    )

    # Assert
    assert staff.can_access_store(store_b.id, date(2026, 2, 5)) is True
    assert store_b.id in staff.current_concurrent_store_ids(date(2026, 2, 5))


def test_staff_deactivate_disables_store_access() -> None:
    # Arrange
    staff = create_staff()
    store = create_store(corporate_id=staff.corporate_id)
    assignment_service = StaffStoreAssignmentService()
    staff = assignment_service.assign_home_store(
        staff, store, start_date=date(2026, 1, 1)
    )

    # Act
    deactivated_staff = staff.deactivate()

    # Assert
    assert deactivated_staff.is_active is False
    assert deactivated_staff.can_access_store(store.id, date(2026, 1, 15)) is False
