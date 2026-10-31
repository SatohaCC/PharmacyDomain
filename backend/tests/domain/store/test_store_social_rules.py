"""店舗（Store）の社会ルール・公費指定・薬局機能認定・安全管理責任者に関するドメインテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.identifiers import StaffId
from app.domain.store.entities import Store, StoreManagerAssignment
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.identifiers import StoreId, StoreManagerAssignmentId
from app.domain.store.primitives import (
    DiseaseCategory,
    PublicExpenseDesignationNumber,
    StoreAddressLine,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.services import StoreManagerAssignmentService
from app.domain.store.value_objects import (
    CommunityLinkageCertification,
    ContactInfo,
    HealthSupportPharmacyNotification,
    ManagerAssignmentPeriod,
    ManagerStaffAffiliation,
    ManagerStaffSource,
    PharmacyCertifications,
    PublicExpenseDesignations,
    SpecializedLinkageCertification,
    StoreAddress,
    StoreNames,
)


def _create_store(
    *,
    corporate_id: CorporateId | None = None,
    public_expense_designations: PublicExpenseDesignations | None = None,
    certifications: PharmacyCertifications | None = None,
    safety_manager_id: StaffId | None = None,
) -> Store:
    cid = corporate_id or CorporateId.generate()
    return Store(
        id=StoreId.generate(),
        corporate_id=cid,
        names=StoreNames(
            name=StoreName("メディカル薬局 中央店"),
            kana=StoreNameKana("メディカルヤッキョク チュウオウテン"),
            romaji=StoreNameRomaji("Medical Pharmacy Chuo"),
        ),
        address=StoreAddress(
            postal_code=StorePostalCode("100-0001"),
            address=StoreAddressLine("東京都千代田区千代田1-1"),
        ),
        contact_info=ContactInfo(
            phone_number=StorePhoneNumber("03-1234-5678"),
        ),
        public_expense_designations=public_expense_designations
        or PublicExpenseDesignations(),
        certifications=certifications or PharmacyCertifications(),
        safety_manager_id=safety_manager_id,
    )


# --- 1. 公費指定医療機関 (PublicExpenseDesignations) のテスト ---


def test_公費指定番号_生活保護や自立支援等の番号_保持できる() -> None:
    # Arrange
    designations = PublicExpenseDesignations(
        public_assistance_number=PublicExpenseDesignationNumber("130001"),
        support_for_independence_number=PublicExpenseDesignationNumber("139999"),
        intractable_disease_number=PublicExpenseDesignationNumber("138888"),
        workers_accident_number=PublicExpenseDesignationNumber("137777"),
    )

    # Act
    store = _create_store(public_expense_designations=designations)

    # Assert
    assert store.public_expense_designations == designations
    assert (
        store.public_expense_designations.public_assistance_number
        == PublicExpenseDesignationNumber("130001")
    )
    assert (
        store.public_expense_designations.support_for_independence_number
        == PublicExpenseDesignationNumber("139999")
    )


# --- 2. 薬局機能認定 (PharmacyCertifications) のテスト ---


def test_地域連携薬局認定_有効期間判定_正しく動作する() -> None:
    # Arrange: 2026/04/01 ~ 2027/03/31
    cert = CommunityLinkageCertification(
        certification_number=PublicExpenseDesignationNumber("CL-2026-001"),
        valid_from=date(2026, 4, 1),
        valid_to=date(2027, 3, 31),
    )

    # Act & Assert
    assert cert.is_effective_on(date(2026, 4, 1)) is True
    assert cert.is_effective_on(date(2026, 10, 1)) is True
    assert cert.is_effective_on(date(2027, 3, 31)) is True
    assert cert.is_effective_on(date(2026, 3, 31)) is False
    assert cert.is_effective_on(date(2027, 4, 1)) is False


def test_専門医療機関連携薬局認定_がん傷病区分と有効性_保持できる() -> None:
    # Arrange: がん専門医療機関連携薬局
    cert = SpecializedLinkageCertification(
        certification_number=PublicExpenseDesignationNumber("SL-2026-002"),
        disease_category=DiseaseCategory.CANCER,
        valid_from=date(2026, 4, 1),
        valid_to=date(2027, 3, 31),
    )

    # Act & Assert
    assert cert.disease_category == DiseaseCategory.CANCER
    assert cert.disease_category.label == "がん"
    assert cert.is_effective_on(date(2026, 6, 1)) is True


def test_店舗_薬局機能認定一式_更新できる() -> None:
    # Arrange
    store = _create_store()
    certifications = PharmacyCertifications(
        community_linkage=CommunityLinkageCertification(
            certification_number=PublicExpenseDesignationNumber("CL-001"),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        ),
        health_support=HealthSupportPharmacyNotification(notified_on=date(2025, 10, 1)),
    )

    # Act
    updated = store.update_certifications(certifications)

    # Assert
    assert updated.certifications.community_linkage is not None
    assert updated.certifications.health_support is not None
    assert updated.certifications.health_support.notified_on == date(2025, 10, 1)


# --- 3. 医薬品安全管理責任者 (Safety Manager) のテスト ---


def test_店舗_安全管理責任者_指名および解任できる() -> None:
    # Arrange
    store = _create_store()
    staff_id = StaffId.generate()
    assert store.safety_manager_id is None

    # Act 1: 指名
    appointed = store.appoint_safety_manager(staff_id)
    assert appointed.safety_manager_id == staff_id

    # Act 2: 解任
    removed = appointed.remove_safety_manager()
    assert removed.safety_manager_id is None


# --- 4. 管理薬剤師の週労働時間（常勤要件・週32時間以上）のテスト ---


def test_管理薬剤師任命_週労働時間が32時間未満_常勤要件違反で拒否される() -> None:
    # Arrange
    store = _create_store()
    staff_id = StaffId.generate()
    assignment = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=store.corporate_id,
        store_id=store.id,
        staff_id=staff_id,
        person_id=AccountPersonId.generate(),
        period=ManagerAssignmentPeriod(starts_on=date(2026, 4, 1)),
    )
    # パート等で週20時間契約のスタッフ
    manager_staff = ManagerStaffSource(
        staff_id=staff_id,
        corporate_id=store.corporate_id,
        staff_is_active=True,
        has_pharmacist=True,
        weekly_contract_hours=Decimal("20.0"),  # 32時間未満
        affiliations=(
            ManagerStaffAffiliation(
                store_id=store.id,
                starts_on=date(2026, 1, 1),
                ends_on=None,
            ),
        ),
    )
    service = StoreManagerAssignmentService()

    # Act / Assert
    with pytest.raises(ManagerAssignmentConflictError) as exc_info:
        service.ensure_assignable(assignment, store=store, staff=manager_staff)
    assert "管理薬剤師は週32時間以上の勤務要件" in str(exc_info.value)
