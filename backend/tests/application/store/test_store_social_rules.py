"""店舗の社会保険・機能認定・安全管理者ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.composition.adapters.organization_snapshot_mapping import (
    ManagerStaffAdapter,
)
from app.application.store.commands.manage_safety_manager import (
    AppointSafetyManagerCommand,
    AppointSafetyManagerUseCase,
    RemoveSafetyManagerCommand,
    RemoveSafetyManagerUseCase,
)
from app.application.store.commands.update_certifications import (
    CommunityLinkageInput,
    HealthSupportNotificationInput,
    SpecializedLinkageInput,
    UpdateCertificationsCommand,
    UpdateCertificationsUseCase,
)
from app.application.store.commands.update_public_expense_designations import (
    UpdatePublicExpenseDesignationsCommand,
    UpdatePublicExpenseDesignationsUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.staff.identifiers import StaffId
from app.domain.store.primitives import DiseaseCategory
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.factories.staff_factory import create_staff
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_update_certifications_success() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = UpdateCertificationsUseCase(
        repository=repository,
        corporate_access=create_vendor_corporate_access(),
    )

    command = UpdateCertificationsCommand(
        corporate_id=str(corporate_id.value),
        store_id=str(store.id.value),
        community_linkage=CommunityLinkageInput(
            certification_number="12345678",
            valid_from=date(2026, 4, 1),
            valid_to=date(2027, 3, 31),
        ),
        specialized_linkage=SpecializedLinkageInput(
            certification_number="87654321",
            disease_category="cancer",
            valid_from=date(2026, 4, 1),
            valid_to=date(2027, 3, 31),
        ),
        health_support=HealthSupportNotificationInput(
            notified_on=date(2026, 1, 15),
        ),
    )

    # Act
    await use_case.execute(command)

    # Assert
    updated = await repository.get(store.id)
    assert updated is not None
    assert updated.certifications.community_linkage is not None
    assert (
        updated.certifications.community_linkage.certification_number.value
        == "12345678"
    )
    assert updated.certifications.specialized_linkage is not None
    assert (
        updated.certifications.specialized_linkage.disease_category
        == DiseaseCategory.CANCER
    )
    assert updated.certifications.health_support is not None
    assert updated.certifications.health_support.notified_on == date(2026, 1, 15)


async def test_update_public_expense_designations_success() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id)
    use_case = UpdatePublicExpenseDesignationsUseCase(
        repository=repository,
        corporate_access=create_vendor_corporate_access(),
    )

    command = UpdatePublicExpenseDesignationsCommand(
        corporate_id=str(corporate_id.value),
        store_id=str(store.id.value),
        public_assistance_number="1234567",
        support_for_independence_number="2345678",
        intractable_disease_number="3456789",
        workers_accident_number="4567890",
    )

    # Act
    await use_case.execute(command)

    # Assert
    updated = await repository.get(store.id)
    assert updated is not None
    assert updated.public_expense_designations.public_assistance_number is not None
    assert (
        updated.public_expense_designations.public_assistance_number.value == "1234567"
    )
    assert (
        updated.public_expense_designations.support_for_independence_number is not None
    )
    assert (
        updated.public_expense_designations.support_for_independence_number.value
        == "2345678"
    )
    assert updated.public_expense_designations.intractable_disease_number is not None
    assert (
        updated.public_expense_designations.intractable_disease_number.value
        == "3456789"
    )
    assert updated.public_expense_designations.workers_accident_number is not None
    assert (
        updated.public_expense_designations.workers_accident_number.value == "4567890"
    )


async def test_appoint_and_remove_safety_manager_success() -> None:
    # Arrange
    store_repo = InMemoryStoreRepository()
    staff_repo = InMemoryStaffRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(store_repo, corporate_id=corporate_id)
    staff = create_staff(corporate_id=corporate_id)
    await staff_repo.save(staff)

    staff_reference = ManagerStaffAdapter(staff_repo)
    appoint_use_case = AppointSafetyManagerUseCase(
        repository=store_repo,
        staff_reference=staff_reference,
        corporate_access=create_vendor_corporate_access(),
    )
    remove_use_case = RemoveSafetyManagerUseCase(
        repository=store_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    # Act 1: Appoint
    await appoint_use_case.execute(
        AppointSafetyManagerCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
            staff_id=str(staff.id.value),
        )
    )

    # Assert 1
    updated = await store_repo.get(store.id)
    assert updated is not None
    assert updated.safety_manager_id == staff.id

    # Act 2: Remove
    await remove_use_case.execute(
        RemoveSafetyManagerCommand(
            corporate_id=str(corporate_id.value),
            store_id=str(store.id.value),
        )
    )

    # Assert 2
    updated = await store_repo.get(store.id)
    assert updated is not None
    assert updated.safety_manager_id is None


async def test_appoint_safety_manager_raises_when_staff_not_found() -> None:
    # Arrange
    store_repo = InMemoryStoreRepository()
    staff_repo = InMemoryStaffRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(store_repo, corporate_id=corporate_id)
    staff_reference = ManagerStaffAdapter(staff_repo)
    appoint_use_case = AppointSafetyManagerUseCase(
        repository=store_repo,
        staff_reference=staff_reference,
        corporate_access=create_vendor_corporate_access(),
    )

    # Act & Assert
    with pytest.raises(DomainValidationError, match="見つかりません"):
        await appoint_use_case.execute(
            AppointSafetyManagerCommand(
                corporate_id=str(corporate_id.value),
                store_id=str(store.id.value),
                staff_id=str(StaffId.generate().value),
            )
        )
