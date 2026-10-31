"""Phase 3: 退職・管理薬剤師・再雇用に関する統合テスト（TC-053〜TC-067）。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.composition.adapters.organization_snapshot_mapping import (
    ManagerStaffAdapter,
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_person_adapter import StaffPersonAdapter
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.identity.commands.change_membership import ChangeMembershipUseCase
from app.application.identity.commands.reactivate_account import (
    ReactivateAccountUseCase,
)
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.staff.commands.activate_staff import (
    ActivateStaffCommand,
    ActivateStaffUseCase,
)
from app.application.staff.commands.deactivate_staff import (
    DeactivateStaffCommand,
    DeactivateStaffUseCase,
)
from app.application.staff.commands.transfer_staff_home_store import (
    TransferStaffHomeStoreCommand,
    TransferStaffHomeStoreUseCase,
)
from app.application.store.commands.manage_store_manager import (
    ManageStoreManagerCommand,
    ManageStoreManagerUseCase,
)
from app.application.store.commands.models import ManagerAction
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
)
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.exceptions import AffiliationDateConflictError
from app.domain.staff.primitives import PharmacistLicenseNumber, StaffEmailAddress
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.entities import StoreManagerAssignment
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.identifiers import StoreManagerAssignmentId
from app.domain.store.value_objects import ManagerAssignmentPeriod
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.application.staff.access_revocation_helpers import create_access_revocation
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
    InMemoryVendorOperatorRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork

_NOW = datetime(2026, 9, 17, 3, 0, tzinfo=UTC)
_TODAY = date(2026, 9, 17)


def _person(corporate_id: CorporateId) -> AccountPerson:
    return AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_TC053_退職_原子的成功_スタッフ停止と所属終了とアカウントメンバーシップ停止が揃って確定する() -> (
    None
):
    """TC-053: 在任任命なしStaffを当日退職すると、Staff停止・所属終了・Account/Membership停止が原子的確定。"""
    corp_id = CorporateId.generate()
    staffs = InMemoryStaffRepository()
    stores = InMemoryStoreRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    links = InMemoryStaffPersonLinkRepository()
    people = InMemoryAccountPersonRepository()

    store = create_store(corporate_id=corp_id, name="第一店舗")
    await stores.save(store)

    staff = replace(
        create_staff(corporate_id=corp_id),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=True,
            ),
        ),
    )
    await staffs.save(staff)

    person = _person(corp_id)
    await people.save(person)

    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
    )
    await accounts.save(account)

    link = StaffPersonLink(id=staff.id, corporate_id=corp_id, person_id=person.id)
    await links.save(link)

    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corp_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({store.id}),
        staff_id=staff.id,
    )
    await memberships.save(membership)

    use_case = DeactivateStaffUseCase(
        repository=staffs,
        corporate_access=create_vendor_corporate_access(),
        access_revocation=create_access_revocation(memberships, accounts),
        clock=FakeClock(_NOW),
    )

    # Act
    await use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            retired_on=_TODAY,
        )
    )

    # Assert
    saved_staff = await staffs.get(corporate_id=corp_id, staff_id=staff.id)
    assert saved_staff is not None
    assert not saved_staff.is_active
    assert saved_staff.affiliations[0].period.end_date == _TODAY

    saved_membership = await memberships.get(membership.id)
    assert saved_membership is not None
    assert saved_membership.status == AccountStatus.SUSPENDED

    saved_account = await accounts.get(account.id)
    assert saved_account is not None
    assert saved_account.status == AccountStatus.SUSPENDED

    # 過去本人対応は保持
    saved_link = await links.get(staff.id)
    assert saved_link is not None
    assert saved_link.person_id == person.id


@pytest.mark.asyncio
async def test_TC055_退職日_未来日は422_当日と整合過去日は200_矛盾過去日は409() -> None:
    """TC-055: 未来退職日は422拒否、当日・整合過去日は200、所属開始より前の矛盾過去日は409。"""
    corp_id = CorporateId.generate()
    staffs = InMemoryStaffRepository()
    stores = InMemoryStoreRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()

    store = create_store(corporate_id=corp_id, name="第一店舗")
    await stores.save(store)

    staff = replace(
        create_staff(corporate_id=corp_id),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 3, 1)),
                is_primary=True,
            ),
        ),
    )
    await staffs.save(staff)

    use_case = DeactivateStaffUseCase(
        repository=staffs,
        corporate_access=create_vendor_corporate_access(),
        access_revocation=create_access_revocation(memberships, accounts),
        clock=FakeClock(_NOW),
    )

    # 1. 未来日 (2026-09-18) -> 422 (DomainValidationError)
    with pytest.raises(DomainValidationError, match="退職日に未来日は指定できません"):
        await use_case.execute(
            DeactivateStaffCommand(
                corporate_id=str(corp_id.value),
                staff_id=str(staff.id.value),
                retired_on=date(2026, 9, 18),
            )
        )

    # 2. 所属開始日より前の矛盾過去日 (2026-02-01 < 2026-03-01) -> 409 (AffiliationDateConflictError)
    with pytest.raises(AffiliationDateConflictError):
        await use_case.execute(
            DeactivateStaffCommand(
                corporate_id=str(corp_id.value),
                staff_id=str(staff.id.value),
                retired_on=date(2026, 2, 1),
            )
        )

    # 3. 整合過去日 (2026-08-31) -> 成功 (200相当)
    await use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            retired_on=date(2026, 8, 31),
        )
    )
    saved = await staffs.get(corporate_id=corp_id, staff_id=staff.id)
    assert saved is not None and not saved.is_active
    assert saved.affiliations[0].period.end_date == date(2026, 8, 31)


@pytest.mark.asyncio
async def test_TC057_法人非干渉_A法人での退職がB法人の同名同メールスタッフに影響しない() -> (
    None
):
    """TC-057: A法人とB法人に同名・同メールのスタッフがいても、A法人の退職でB法人は一切不変。"""
    corp_a = CorporateId.generate()
    corp_b = CorporateId.generate()
    staffs = InMemoryStaffRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()

    email = StaffEmailAddress("pharmacist@example.test")

    # 法人A
    staff_a = replace(create_staff(corporate_id=corp_a), email=email)
    await staffs.save(staff_a)
    account_a = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_a,
        person_id=AccountPersonId.generate(),
    )
    await accounts.save(account_a)
    mem_a = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account_a.id,
        corporate_id=corp_a,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
        staff_id=staff_a.id,
    )
    await memberships.save(mem_a)

    # 法人B
    staff_b = replace(create_staff(corporate_id=corp_b), email=email)
    await staffs.save(staff_b)
    account_b = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_b,
        person_id=AccountPersonId.generate(),
    )
    await accounts.save(account_b)
    mem_b = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account_b.id,
        corporate_id=corp_b,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
        staff_id=staff_b.id,
    )
    await memberships.save(mem_b)

    use_case = DeactivateStaffUseCase(
        repository=staffs,
        corporate_access=create_vendor_corporate_access(),
        access_revocation=create_access_revocation(memberships, accounts),
        clock=FakeClock(_NOW),
    )

    # Act: 法人Aのスタッフのみ退職
    await use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(corp_a.value),
            staff_id=str(staff_a.id.value),
            retired_on=_TODAY,
        )
    )

    # Assert: 法人Aは停止
    saved_a = await staffs.get(corporate_id=corp_a, staff_id=staff_a.id)
    assert saved_a is not None and not saved_a.is_active
    saved_mem_a = await memberships.get(mem_a.id)
    assert saved_mem_a is not None and saved_mem_a.status == AccountStatus.SUSPENDED
    saved_acc_a = await accounts.get(account_a.id)
    assert saved_acc_a is not None and saved_acc_a.status == AccountStatus.SUSPENDED

    # Assert: 法人Bは完全に有効のまま不変
    saved_b = await staffs.get(corporate_id=corp_b, staff_id=staff_b.id)
    assert saved_b is not None and saved_b.is_active
    saved_mem_b = await memberships.get(mem_b.id)
    assert saved_mem_b is not None and saved_mem_b.status == AccountStatus.ACTIVE
    saved_acc_b = await accounts.get(account_b.id)
    assert saved_acc_b is not None and saved_acc_b.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_TC058_TC059_現職管理薬剤師の退職拒否と閉区間境界() -> None:
    """TC-058/059: 未終了任命があるスタッフは退職拒否(409)。終了日当日退職は可、翌日終了は拒否。"""
    from app.application.composition.adapters.staff_integrity import (
        StaffAssignmentWriteGuard,
    )

    corp_id = CorporateId.generate()
    stores = InMemoryStoreRepository()
    managers = InMemoryStoreManagerAssignmentRepository()
    store = create_store(corporate_id=corp_id)
    await stores.save(store)

    staff = replace(
        create_staff(
            corporate_id=corp_id,
            qualifications=StaffQualifications.from_profiles(
                PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
            ),
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=True,
            ),
        ),
    )
    person_id = AccountPersonId.generate()

    guard = StaffAssignmentWriteGuard(
        stores, managers, FakeClock(_NOW), FakeOrganizationLock()
    )

    # 1. 未終了任命 (ends_on=None) -> 退職拒否
    assignment = StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=corp_id,
        store_id=store.id,
        staff_id=staff.id,
        person_id=person_id,
        period=ManagerAssignmentPeriod(starts_on=date(2026, 1, 1), ends_on=None),
    )
    await managers.save(assignment)

    with pytest.raises(ManagerAssignmentConflictError):
        await guard.check(staff.deactivate(_TODAY), False)

    # 2. 翌日終了 (ends_on=2026-09-18 > 2026-09-17) -> 退職拒否
    tomorrow_assignment = replace(
        assignment,
        period=ManagerAssignmentPeriod(
            starts_on=date(2026, 1, 1), ends_on=date(2026, 9, 18)
        ),
    )
    await managers.save(tomorrow_assignment)
    with pytest.raises(ManagerAssignmentConflictError):
        await guard.check(staff.deactivate(_TODAY), False)

    # 3. 当日終了 (ends_on=2026-09-17) -> 当日退職可能（閉区間の最終日満了と整合）
    today_ended = replace(
        assignment,
        period=ManagerAssignmentPeriod(starts_on=date(2026, 1, 1), ends_on=_TODAY),
    )
    await managers.save(today_ended)
    # 例外なく成功
    await guard.check(staff.deactivate(_TODAY), False)


@pytest.mark.asyncio
async def test_TC060_正規交代_前任終了と後任開始は前日と当日で連続し境界日に在任の欠落や重複がない() -> (
    None
):
    """TC-060: 管理薬剤師の交代では前任終了が後任開始の前日となり、期間の重複も欠落もない。"""
    corp_id = CorporateId.generate()
    stores = InMemoryStoreRepository()
    managers = InMemoryStoreManagerAssignmentRepository()
    staffs = InMemoryStaffRepository()
    links = InMemoryStaffPersonLinkRepository()
    store = create_store(corporate_id=corp_id)
    await stores.save(store)

    person1 = AccountPersonId.generate()
    person2 = AccountPersonId.generate()
    staff1 = replace(
        create_staff(corporate_id=corp_id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("111111"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=True,
            ),
        ),
    )
    staff2 = replace(
        create_staff(corporate_id=corp_id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("222222"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=True,
            ),
        ),
    )
    await staffs.save(staff1)
    await staffs.save(staff2)
    await links.save(
        StaffPersonLink(id=staff1.id, corporate_id=corp_id, person_id=person1)
    )
    await links.save(
        StaffPersonLink(id=staff2.id, corporate_id=corp_id, person_id=person2)
    )

    use_case = ManageStoreManagerUseCase(
        stores=stores,
        staff=ManagerStaffAdapter(staffs),
        managers=managers,
        people=StaffPersonAdapter(links),
        access=create_vendor_corporate_access(),
        clock=FakeClock(_NOW),
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
    )

    # 1. 前任の任命 (2026-09-01 〜)
    first_res = await use_case.execute(
        ManageStoreManagerCommand(
            corporate_id=str(corp_id.value),
            store_id=str(store.id.value),
            staff_id=str(staff1.id.value),
            action=ManagerAction.APPOINT,
            starts_on=date(2026, 9, 1),
        )
    )

    # 2. 交代: 後任開始日 2026-09-20
    await use_case.execute(
        ManageStoreManagerCommand(
            corporate_id=str(corp_id.value),
            store_id=str(store.id.value),
            assignment_id=first_res.id,
            staff_id=str(staff2.id.value),
            action=ManagerAction.REPLACE,
            starts_on=date(2026, 9, 20),
        )
    )

    # Assert: 境界日の在任
    # 前任最終日 (2026-09-19): 前任のみ在任
    effective_19 = await managers.find_effective(corp_id, store.id, date(2026, 9, 19))
    assert effective_19 is not None and effective_19.staff_id == staff1.id

    # 後任初日 (2026-09-20): 後任のみ在任
    effective_20 = await managers.find_effective(corp_id, store.id, date(2026, 9, 20))
    assert effective_20 is not None and effective_20.staff_id == staff2.id


@pytest.mark.asyncio
async def test_TC066_再雇用_段階的権限_各段階で権限を検証し自動復活しない() -> None:
    """TC-066: 再雇用ではStaff再開→所属設定→Account再開→Membership明示再付与の順に進み、各段階で自動権限復活がない。"""
    corp_id = CorporateId.generate()
    staffs = InMemoryStaffRepository()
    stores = InMemoryStoreRepository()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    people = InMemoryAccountPersonRepository()
    links = InMemoryStaffPersonLinkRepository()
    managers = InMemoryStoreManagerAssignmentRepository()

    store = create_store(corporate_id=corp_id, name="第一店舗")
    await stores.save(store)

    staff = replace(
        create_staff(corporate_id=corp_id),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                is_primary=True,
            ),
        ),
    )
    await staffs.save(staff)

    person = _person(corp_id)
    await people.save(person)

    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
    )
    await accounts.save(account)

    link = StaffPersonLink(id=staff.id, corporate_id=corp_id, person_id=person.id)
    await links.save(link)

    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corp_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({store.id}),
        staff_id=staff.id,
    )
    await memberships.save(membership)

    corp_access = create_vendor_corporate_access()
    clock = FakeClock(_NOW)

    # まず退職実行
    deactivate_use_case = DeactivateStaffUseCase(
        repository=staffs,
        corporate_access=corp_access,
        access_revocation=create_access_revocation(memberships, accounts),
        clock=clock,
    )
    await deactivate_use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            retired_on=_TODAY,
        )
    )

    # 退職状態確認
    retired_staff = await staffs.get(corporate_id=corp_id, staff_id=staff.id)
    assert retired_staff is not None and not retired_staff.is_active
    retired_acc = await accounts.get(account.id)
    assert retired_acc is not None and retired_acc.status == AccountStatus.SUSPENDED
    retired_mem = await memberships.get(membership.id)
    assert retired_mem is not None and retired_mem.status == AccountStatus.SUSPENDED

    _NEXT_DAY = date(2026, 9, 18)

    # 段階1: Staff再開（ActivateStaffUseCase）
    activate_use_case = ActivateStaffUseCase(
        repository=staffs,
        corporate_access=corp_access,
    )
    await activate_use_case.execute(
        ActivateStaffCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
        )
    )
    stage1_staff = await staffs.get(corporate_id=corp_id, staff_id=staff.id)
    assert stage1_staff is not None and stage1_staff.is_active
    # 退職後の日付では所属を持たない（自動で所属・アカウント・メンバーシップは復活しない）
    assert stage1_staff.current_home_store_id(_NEXT_DAY) is None
    stage1_acc = await accounts.get(account.id)
    assert stage1_acc is not None and stage1_acc.status == AccountStatus.SUSPENDED
    stage1_mem = await memberships.get(membership.id)
    assert stage1_mem is not None and stage1_mem.status == AccountStatus.SUSPENDED

    # 段階2: 所属再設定（TransferStaffHomeStoreUseCase）
    transfer_use_case = TransferStaffHomeStoreUseCase(
        staff_repository=staffs,
        store_repository=StaffStoreAdapter(stores),
        assignment_service=StaffStoreAssignmentService(),
        corporate_access=corp_access,
    )
    await transfer_use_case.execute(
        TransferStaffHomeStoreCommand(
            corporate_id=str(corp_id.value),
            staff_id=str(staff.id.value),
            new_store_id=str(store.id.value),
            transfer_date=_NEXT_DAY,
        )
    )
    stage2_staff = await staffs.get(corporate_id=corp_id, staff_id=staff.id)
    assert stage2_staff is not None
    assert stage2_staff.current_home_store_id(_NEXT_DAY) == store.id
    # アカウント・メンバーシップはまだ停止のまま
    stage2_acc = await accounts.get(account.id)
    assert stage2_acc is not None and stage2_acc.status == AccountStatus.SUSPENDED

    # 段階3: アカウント明示再開（ReactivateAccountUseCase）
    repos = IdentityRepositories(
        accounts=accounts,
        people=people,
        memberships=memberships,
        links=links,
        vendor_operators=InMemoryVendorOperatorRepository(),
    )
    reactivate_acc_use_case = ReactivateAccountUseCase(
        repositories=repos,
        access=corp_access,
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
    )
    await reactivate_acc_use_case.execute(str(account.id.value))
    stage3_acc = await accounts.get(account.id)
    assert stage3_acc is not None and stage3_acc.status == AccountStatus.ACTIVE
    # メンバーシップはまだ停止のまま（自動復活なし）
    stage3_mem = await memberships.get(membership.id)
    assert stage3_mem is not None and stage3_mem.status == AccountStatus.SUSPENDED

    # 段階4: メンバーシップ明示再開（ChangeMembershipUseCase）
    change_mem_use_case = ChangeMembershipUseCase(
        repositories=repos,
        staff=staffs,
        stores=stores,
        access=corp_access,
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
        managers=managers,
        clock=clock,
    )
    await change_mem_use_case.execute(
        corporate_id=str(corp_id.value),
        membership_id=str(membership.id.value),
        status="active",
        store_ids=(str(store.id.value),),
    )
    final_mem = await memberships.get(membership.id)
    assert final_mem is not None and final_mem.status == AccountStatus.ACTIVE
    assert store.id in final_mem.active_store_ids

    # IDと本人対応・過去整合性は完全に維持されている
    assert stage1_staff.id == staff.id
    assert stage3_acc.id == account.id
    assert stage3_acc.person_id == person.id
    assert final_mem.id == membership.id


@pytest.mark.asyncio
async def test_TC067_再開_管理権限境界_店舗管理者の範囲外は403_他法人は404_自法人管理者は成功() -> (
    None
):
    """TC-067: 店舗管理者のAccount/他店舗再開は403、他法人アカウントは404、自法人の法人管理者は成功。"""
    corp_a = CorporateId.generate()
    corp_b = CorporateId.generate()
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    people = InMemoryAccountPersonRepository()
    links = InMemoryStaffPersonLinkRepository()

    # 法人Aのアカウント
    person_a = _person(corp_a)
    await people.save(person_a)
    account_a = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_a,
        person_id=person_a.id,
        status=AccountStatus.SUSPENDED,
    )
    await accounts.save(account_a)

    # 法人Bのアカウント
    person_b = _person(corp_b)
    await people.save(person_b)
    account_b = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_b,
        person_id=person_b.id,
        status=AccountStatus.SUSPENDED,
    )
    await accounts.save(account_b)

    repos = IdentityRepositories(
        accounts=accounts,
        people=people,
        memberships=memberships,
        links=links,
        vendor_operators=InMemoryVendorOperatorRepository(),
    )
    corp_repo = AutoProvisioningCorporateRepository()

    # 1. 店舗管理者のアクセス境界（MANAGE_STAFF権限なし） -> 403 (AuthorizationError)
    store_operator_auth = AuthorizationService(
        ActorContext(
            principal_id="store-operator",
            roles=frozenset({ActorRole.STORE_OPERATOR}),
            corporate_id=corp_a,
        )
    )
    store_operator_access = CorporateAccessService(corp_repo, store_operator_auth)
    use_case_op = ReactivateAccountUseCase(
        repositories=repos,
        access=store_operator_access,
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
    )
    with pytest.raises(AuthorizationError):
        await use_case_op.execute(str(account_a.id.value))

    # 2. 法人Aの法人管理者が法人Bのアカウントを再開しようとする -> 404 (NotFoundError)
    corp_a_admin_auth = AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="admin-a",
            corporate_id=corp_a,
        )
    )
    corp_a_admin_access = CorporateAccessService(corp_repo, corp_a_admin_auth)
    use_case_admin_a = ReactivateAccountUseCase(
        repositories=repos,
        access=corp_a_admin_access,
        unit_of_work=NullUnitOfWork(),
        lock=FakeOrganizationLock(),
    )
    with pytest.raises(NotFoundError):
        await use_case_admin_a.execute(str(account_b.id.value))

    # 3. 法人Aの法人管理者が法人Aのアカウントを再開する -> 成功 (200)
    res = await use_case_admin_a.execute(str(account_a.id.value))
    assert res.status == "active"
    saved = await accounts.get(account_a.id)
    assert saved is not None and saved.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_TC056_既存セッション_退職後は古いトークンでの解決が拒否され即時失効する() -> (
    None
):
    """TC-056: 退職前tokenを保有していても、退職確定後にResolveActorUseCaseがUnavailableIdentityErrorを返して即時失効する。"""
    from app.application.identity.boundary_models import VerifiedSubject
    from app.application.identity.errors import UnavailableIdentityError
    from app.application.identity.interfaces.resolve_actor_query_reader import (
        ResolveActorQueryReader,
    )
    from app.application.identity.queries.dtos.identity_resolution import (
        IdentityResolutionSnapshot,
        MembershipIdentitySnapshot,
    )
    from app.application.identity.queries.resolve_actor import ResolveActorUseCase
    from app.domain.identity.primitives import ExternalSubjectKey

    subject_key = ExternalSubjectKey("issuer/retiring-user")
    verified_subject = VerifiedSubject(principal_id=subject_key.value)

    person_id = AccountPersonId.generate()
    account_id = UserAccountId.generate()
    corp_id = CorporateId.generate()
    membership_id = CorporateMembershipId.generate()

    # 退職前: ACTIVE
    active_snapshot = IdentityResolutionSnapshot(
        account_id=account_id,
        account_person_id=person_id,
        person_id=person_id,
        external_subject=subject_key,
        account_status=AccountStatus.ACTIVE,
        is_vendor_admin=False,
        membership=MembershipIdentitySnapshot(
            id=membership_id,
            account_id=account_id,
            corporate_id=corp_id,
            role=MembershipRole.STORE_OPERATOR,
            status=AccountStatus.ACTIVE,
            store_ids=frozenset(),
            suspended_store_ids=frozenset(),
            manager_assignments=(),
            staff_id=None,
        ),
    )

    class FakeIdentityReader(ResolveActorQueryReader):
        def __init__(self, snap: IdentityResolutionSnapshot) -> None:
            self.snap = snap

        async def get_by_subject(
            self, subject: ExternalSubjectKey
        ) -> IdentityResolutionSnapshot | None:
            return self.snap

    reader = FakeIdentityReader(active_snapshot)
    resolver = ResolveActorUseCase(reader, FakeClock(_NOW))

    # 退職前は解決できる
    resolved = await resolver.execute(verified_subject)
    assert resolved.account_id == account_id

    # 退職後: Account と Membership が SUSPENDED
    assert active_snapshot.membership is not None
    retired_snapshot = replace(
        active_snapshot,
        account_status=AccountStatus.SUSPENDED,
        membership=replace(
            active_snapshot.membership,
            status=AccountStatus.SUSPENDED,
        ),
    )
    reader.snap = retired_snapshot

    # 退職後は同じトークン（VerifiedSubject）での解決が拒否され即時失効
    with pytest.raises(UnavailableIdentityError):
        await resolver.execute(verified_subject)
