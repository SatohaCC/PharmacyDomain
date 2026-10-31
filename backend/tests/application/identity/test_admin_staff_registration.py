"""初期管理者ブートストラップと初期スタッフ登録（TC-046, TC-047）のテスト。"""

from __future__ import annotations

import pytest

from app.application.access_control.boundary_models import ActorRole
from app.application.common.exceptions import NotFoundError
from app.application.composition.adapters.contract_admin import ContractAdminAdapter
from app.application.composition.adapters.organization_snapshot_mapping import (
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_creator import StaffCreationAdapter
from app.application.composition.commands.register_contract import (
    RegisterContractCommand,
    RegisterContractUseCase,
)
from app.application.corporate.commands.register_corporate import (
    RegisterCorporateUseCase,
)
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.commands.models import PersonNamesInput
from app.application.identity.commands.register_person import RegisterPersonUseCase
from app.application.identity.commands.register_staff_for_admin import (
    RegisterStaffForAdminCommand,
    RegisterStaffForAdminUseCase,
)
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.identity.entities import AccountPerson, CorporateMembership, UserAccount
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
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
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.staff.value_objects import PharmacistProfile
from app.infrastructure.readers.identity_resolve_actor import ResolveActorProjection
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.fakes.in_memory_identity_repositories import (
    FakeCredentialWriter,
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


@pytest.mark.asyncio
async def test_tc046_初期管理者ブートストラップ_契約作成から初期管理者解決() -> None:
    """TC-046: 運営者がcontracts作成→Staffなし初期管理者が生成。

    店舗未選択でも法人管理可、店舗・薬剤師業務権限は持たない。
    """
    corp_repo = InMemoryCorporateRepository()
    people_repo = InMemoryAccountPersonRepository()
    account_repo = InMemoryUserAccountRepository()
    membership_repo = InMemoryCorporateMembershipRepository()
    vendor_repo = InMemoryVendorOperatorRepository()
    credential_writer = FakeCredentialWriter()
    uow = NullUnitOfWork()
    access = create_vendor_corporate_access()

    # 1. 契約作成ユースケースを構築
    corp_use_case = RegisterCorporateUseCase(
        repository=corp_repo,
        uniqueness_service=CorporateNameUniquenessService(corp_repo),
        corporate_access=access,
    )
    person_use_case = RegisterPersonUseCase(
        people=people_repo,
        access=access,
        unit_of_work=uow,
    )
    admin_op = ContractAdminAdapter(
        accounts=account_repo,
        memberships=membership_repo,
        credentials=credential_writer,
    )
    register_contract_uc = RegisterContractUseCase(
        corporate=corp_use_case,
        person=person_use_case,
        admin_user=admin_op,
        unit_of_work=uow,
    )

    # 2. 契約作成を実行
    cmd = RegisterContractCommand(
        name="テスト薬局株式会社",
        representative_last_name="代表",
        representative_first_name="太郎",
        administrator=PersonNamesInput(
            last_name="管理",
            first_name="一郎",
            last_name_kana="カンリ",
            first_name_kana="イチロウ",
        ),
        email="admin@test-pharmacy.example.test",
        initial_password="AdminPassword123!",
    )
    result = await register_contract_uc.execute(cmd)

    # 法人・本人・Account・Membership・Credentialが原子的生成されている
    corp_id = CorporateId.parse(result.id)
    account_id = UserAccountId.parse(result.account_id)

    corporate = await corp_repo.get(corp_id)
    assert corporate is not None
    assert corporate.name.value == "テスト薬局株式会社"

    account = await account_repo.get(account_id)
    assert account is not None
    assert account.corporate_id == corp_id
    assert account.status == AccountStatus.ACTIVE

    person = await people_repo.get(account.person_id)
    assert person is not None
    assert person.corporate_id == corp_id
    assert person.names.kanji.last_name.value == "管理"
    assert person.names.kanji.first_name.value == "一郎"

    memberships = await membership_repo.list_by_corporate(corp_id)
    assert len(memberships) == 1
    admin_membership = memberships[0]
    assert admin_membership.account_id == account_id
    assert admin_membership.role == MembershipRole.CORPORATE_ADMIN
    assert admin_membership.staff_id is None  # Staffなし
    assert admin_membership.store_ids == frozenset()

    assert account.external_subject is not None
    assert len(credential_writer.issued) == 1
    issued_corp, issued_email, _, issued_subject = credential_writer.issued[0]
    assert issued_corp == corp_id
    assert issued_email == "admin@test-pharmacy.example.test"
    assert issued_subject == account.external_subject.value

    # 3. 初期管理者のActor解決: 法人管理ロールを持ち、店舗権限は持たない
    manager_assignments = InMemoryStoreManagerAssignmentRepository()
    clock = FakeClock()
    reader = ResolveActorProjection(
        people=people_repo,
        accounts=account_repo,
        memberships=membership_repo,
        managers=manager_assignments,
        vendor_operators=vendor_repo,
    )
    resolve_actor_uc = ResolveActorUseCase(reader=reader, clock=clock)
    actor_context = await resolve_actor_uc.execute(
        VerifiedSubject(
            principal_id=account.external_subject.value,
        )
    )

    assert ActorRole.CORPORATE_ADMIN in actor_context.roles
    assert ActorRole.STORE_OPERATOR not in actor_context.roles
    assert ActorRole.STORE_MANAGER not in actor_context.roles
    assert actor_context.corporate_id == corp_id
    assert actor_context.person_id == person.id
    assert actor_context.account_id == account.id
    assert actor_context.staff_id is None
    assert actor_context.store_ids == frozenset()
    assert actor_context.managed_store_ids == frozenset()


@pytest.mark.asyncio
async def test_tc047_初期管理者へのスタッフ登録_名前引き継ぎと正常登録() -> None:
    """TC-047: 初期管理者へのスタッフ登録（名前省略で本人氏名引き継ぎ、資格情報登録、StaffPersonLink生成、Membership.staff_id更新）。"""
    corp_id = CorporateId.generate()
    people_repo = InMemoryAccountPersonRepository()
    account_repo = InMemoryUserAccountRepository()
    membership_repo = InMemoryCorporateMembershipRepository()
    link_repo = InMemoryStaffPersonLinkRepository()
    vendor_repo = InMemoryVendorOperatorRepository()
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uow = NullUnitOfWork()
    lock = FakeOrganizationLock()
    access = create_vendor_corporate_access()

    # 初期管理者を作成
    person = AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corp_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("管理"),
                first_name=PersonNamePart("一郎"),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("カンリ"),
                first_name=PersonNameKanaPart("イチロウ"),
            ),
        ),
    )
    await people_repo.save(person)

    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
        status=AccountStatus.ACTIVE,
        external_subject=ExternalSubjectKey("local:admin-1"),
    )
    await account_repo.save(account)

    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corp_id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=None,
    )
    await membership_repo.save(membership)

    repositories = IdentityRepositories(
        people_repo,
        account_repo,
        membership_repo,
        link_repo,
        vendor_repo,
    )
    staff_creator = StaffCreationAdapter(
        staff_repository=staff_repo,
        store_repository=StaffStoreAdapter(store_repo),
        uniqueness_service=StaffCodeUniquenessService(staff_repo),
        assignment_service=StaffStoreAssignmentService(),
    )
    use_case = RegisterStaffForAdminUseCase(
        repositories=repositories,
        corporate_access=access,
        staff_creator=staff_creator,
        unit_of_work=uow,
        lock=lock,
    )

    # 1. 名前省略で登録（本人氏名を引き継ぐ）
    cmd = RegisterStaffForAdminCommand(
        corporate_id=str(corp_id.value),
        membership_id=str(membership.id.value),
        code="ADMIN-001",
        pharmacist_license_number="123456",
    )
    staff_id = await use_case.execute(cmd)

    # スタッフの確認
    staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff_id)
    assert staff is not None
    assert staff.names.kanji.last_name.value == "管理"
    assert staff.names.kanji.first_name.value == "一郎"
    assert staff.names.kana.last_name.value == "カンリ"
    assert staff.names.kana.first_name.value == "イチロウ"
    pharmacist_profile = staff.qualifications.get(PharmacistProfile)
    assert pharmacist_profile is not None
    assert pharmacist_profile.license_number.value == "123456"

    # StaffPersonLinkの確認
    link = await link_repo.get(staff_id)
    assert link is not None
    assert link.corporate_id == corp_id
    assert link.person_id == person.id
    assert link.id == staff_id

    # Membership.staff_idの更新確認
    updated_membership = await membership_repo.get(membership.id)
    assert updated_membership is not None
    assert updated_membership.staff_id == staff_id

    # 別Account/Personが増えていないことを確認
    assert len(people_repo.items) == 1
    assert len(account_repo.items) == 1


@pytest.mark.asyncio
async def test_tc047_初期管理者へのスタッフ登録_名前明示指定() -> None:
    """TC-047: 名前を明示指定した場合、その名前でスタッフが登録される。"""
    corp_id = CorporateId.generate()
    people_repo = InMemoryAccountPersonRepository()
    account_repo = InMemoryUserAccountRepository()
    membership_repo = InMemoryCorporateMembershipRepository()
    link_repo = InMemoryStaffPersonLinkRepository()
    vendor_repo = InMemoryVendorOperatorRepository()
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uow = NullUnitOfWork()
    lock = FakeOrganizationLock()
    access = create_vendor_corporate_access()

    person = AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corp_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("管理"),
                first_name=PersonNamePart("一郎"),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("カンリ"),
                first_name=PersonNameKanaPart("イチロウ"),
            ),
        ),
    )
    await people_repo.save(person)

    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
        status=AccountStatus.ACTIVE,
        external_subject=ExternalSubjectKey("local:admin-2"),
    )
    await account_repo.save(account)

    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corp_id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=None,
    )
    await membership_repo.save(membership)

    use_case = RegisterStaffForAdminUseCase(
        repositories=IdentityRepositories(
            people_repo,
            account_repo,
            membership_repo,
            link_repo,
            vendor_repo,
        ),
        corporate_access=access,
        staff_creator=StaffCreationAdapter(
            staff_repository=staff_repo,
            store_repository=StaffStoreAdapter(store_repo),
            uniqueness_service=StaffCodeUniquenessService(staff_repo),
            assignment_service=StaffStoreAssignmentService(),
        ),
        unit_of_work=uow,
        lock=lock,
    )

    cmd = RegisterStaffForAdminCommand(
        corporate_id=str(corp_id.value),
        membership_id=str(membership.id.value),
        last_name="別姓",
        first_name="次郎",
        last_name_kana="ベッセイ",
        first_name_kana="ジロウ",
        code="ADMIN-002",
    )
    staff_id = await use_case.execute(cmd)

    staff = await staff_repo.get(corporate_id=corp_id, staff_id=staff_id)
    assert staff is not None
    assert staff.names.kanji.last_name.value == "別姓"
    assert staff.names.kanji.first_name.value == "次郎"


@pytest.mark.asyncio
async def test_tc047_初期管理者へのスタッフ登録_二重登録で409() -> None:
    """TC-047: 既にスタッフが紐付いているメンバーシップへの再登録は409（IdentityConflictError）。"""
    corp_id = CorporateId.generate()
    people_repo = InMemoryAccountPersonRepository()
    account_repo = InMemoryUserAccountRepository()
    membership_repo = InMemoryCorporateMembershipRepository()
    link_repo = InMemoryStaffPersonLinkRepository()
    vendor_repo = InMemoryVendorOperatorRepository()
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uow = NullUnitOfWork()
    lock = FakeOrganizationLock()
    access = create_vendor_corporate_access()

    person = AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corp_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("管理"),
                first_name=PersonNamePart("一郎"),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("カンリ"),
                first_name=PersonNameKanaPart("イチロウ"),
            ),
        ),
    )
    await people_repo.save(person)

    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
        status=AccountStatus.ACTIVE,
        external_subject=ExternalSubjectKey("local:admin-3"),
    )
    await account_repo.save(account)

    use_case = RegisterStaffForAdminUseCase(
        repositories=IdentityRepositories(
            people_repo,
            account_repo,
            membership_repo,
            link_repo,
            vendor_repo,
        ),
        corporate_access=access,
        staff_creator=StaffCreationAdapter(
            staff_repository=staff_repo,
            store_repository=StaffStoreAdapter(store_repo),
            uniqueness_service=StaffCodeUniquenessService(staff_repo),
            assignment_service=StaffStoreAssignmentService(),
        ),
        unit_of_work=uow,
        lock=lock,
    )

    # 既にstaff_idを持つメンバーシップ
    from app.domain.staff.identifiers import StaffId

    membership_with_staff = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corp_id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=StaffId.generate(),
    )
    await membership_repo.save(membership_with_staff)

    cmd = RegisterStaffForAdminCommand(
        corporate_id=str(corp_id.value),
        membership_id=str(membership_with_staff.id.value),
    )
    with pytest.raises(IdentityConflictError, match="既にスタッフが登録されています"):
        await use_case.execute(cmd)


@pytest.mark.asyncio
async def test_tc047_初期管理者へのスタッフ登録_別法人や存在しないメンバーシップで404() -> (
    None
):
    """TC-047: 別法人のメンバーシップ指定、または存在しないIDの指定は404（NotFoundError）。"""
    corp_a = CorporateId.generate()
    corp_b = CorporateId.generate()
    people_repo = InMemoryAccountPersonRepository()
    account_repo = InMemoryUserAccountRepository()
    membership_repo = InMemoryCorporateMembershipRepository()
    link_repo = InMemoryStaffPersonLinkRepository()
    vendor_repo = InMemoryVendorOperatorRepository()
    staff_repo = InMemoryStaffRepository()
    store_repo = InMemoryStoreRepository()
    uow = NullUnitOfWork()
    lock = FakeOrganizationLock()
    access = create_vendor_corporate_access()

    person_b = AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corp_b,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("法人B"),
                first_name=PersonNamePart("管理者"),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ホウジンビー"),
                first_name=PersonNameKanaPart("カンリシャ"),
            ),
        ),
    )
    await people_repo.save(person_b)

    account_b = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_b,
        person_id=person_b.id,
        status=AccountStatus.ACTIVE,
        external_subject=ExternalSubjectKey("local:admin-b"),
    )
    await account_repo.save(account_b)

    membership_b = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account_b.id,
        corporate_id=corp_b,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
        staff_id=None,
    )
    await membership_repo.save(membership_b)

    use_case = RegisterStaffForAdminUseCase(
        repositories=IdentityRepositories(
            people_repo,
            account_repo,
            membership_repo,
            link_repo,
            vendor_repo,
        ),
        corporate_access=access,
        staff_creator=StaffCreationAdapter(
            staff_repository=staff_repo,
            store_repository=StaffStoreAdapter(store_repo),
            uniqueness_service=StaffCodeUniquenessService(staff_repo),
            assignment_service=StaffStoreAssignmentService(),
        ),
        unit_of_work=uow,
        lock=lock,
    )

    # 1. 存在しないメンバーシップ
    cmd_not_found = RegisterStaffForAdminCommand(
        corporate_id=str(corp_a.value),
        membership_id=str(CorporateMembershipId.generate().value),
    )
    with pytest.raises(NotFoundError):
        await use_case.execute(cmd_not_found)

    # 2. 別法人Bのメンバーシップを法人Aから指定
    cmd_cross_corp = RegisterStaffForAdminCommand(
        corporate_id=str(corp_a.value),
        membership_id=str(membership_b.id.value),
    )
    with pytest.raises(NotFoundError):
        await use_case.execute(cmd_cross_corp)
