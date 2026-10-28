"""Staff エンティティおよびドメインモデルの動作テスト。"""

from __future__ import annotations

from datetime import date

from app.application.composition.adapters.organization_snapshot_mapping import (
    staff_store_source,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.primitives import (
    InsurancePharmacistRegistrationNumber,
    PharmacistLicenseNumber,
)
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.staff.value_objects import (
    InsurancePharmacistRegistration,
    PharmacistProfile,
    StaffQualifications,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store


def test_staff_pharmacist_qualification() -> None:
    # Arrange
    license_num = PharmacistLicenseNumber("123456")
    insurance_reg = InsurancePharmacistRegistration(
        registration_number=InsurancePharmacistRegistrationNumber("REG-123"),
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


def test_スタッフの所属導出_主所属と兼務が対象日から導出される() -> None:
    # Arrange
    corp_id = CorporateId.generate()
    store_a = create_store(corporate_id=corp_id, name="店舗A")
    store_b = create_store(corporate_id=corp_id, name="店舗B")
    assignment_service = StaffStoreAssignmentService()

    staff = create_staff(corporate_id=corp_id)

    # Act: store_a に主所属を設定
    staff = assignment_service.assign_home_store(
        staff, staff_store_source(store_a), start_date=date(2026, 1, 1)
    )

    # Assert
    assert staff.current_home_store_id(date(2026, 1, 15)) == store_a.id
    assert staff.current_concurrent_store_ids(date(2026, 1, 15)) == frozenset()

    # Act: store_b に兼務追加
    staff = assignment_service.assign_concurrent_store(
        staff, staff_store_source(store_b), start_date=date(2026, 2, 1)
    )

    # Assert
    assert staff.current_home_store_id(date(2026, 2, 5)) == store_a.id
    assert staff.current_concurrent_store_ids(date(2026, 2, 5)) == frozenset(
        {store_b.id}
    )
