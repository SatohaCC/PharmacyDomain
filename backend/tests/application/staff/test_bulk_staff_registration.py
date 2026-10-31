"""スタッフ・アカウント一括登録（TC-030〜TC-033）のApplication層テスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.composition.adapters.organization_snapshot_mapping import (
    StaffStoreAdapter,
)
from app.application.composition.adapters.staff_account_registration import (
    StaffAccountRegistrationAdapter,
)
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.staff.commands.register_staff import (
    BulkRegisteredStaffResult,
    BulkStaffAccountInput,
    RegisterStaffCommand,
    RegisterStaffUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    FakeCredentialWriter,
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


class _Fixture:
    def __init__(self, actor_context: ResolvedActorContext | None = None) -> None:
        self.staff_repo = InMemoryStaffRepository()
        self.store_repo = InMemoryStoreRepository()
        self.people_repo = InMemoryAccountPersonRepository()
        self.account_repo = InMemoryUserAccountRepository()
        self.membership_repo = InMemoryCorporateMembershipRepository()
        self.link_repo = InMemoryStaffPersonLinkRepository()
        self.credentials = FakeCredentialWriter()
        self.corp_repo = AutoProvisioningCorporateRepository()

        adapter = StaffAccountRegistrationAdapter(
            people=self.people_repo,
            accounts=self.account_repo,
            memberships=self.membership_repo,
            links=self.link_repo,
            credentials=self.credentials,
        )

        corporate_access = (
            CorporateAccessService(self.corp_repo, AuthorizationService(actor_context))
            if actor_context is not None
            else create_vendor_corporate_access()
        )

        self.use_case = RegisterStaffUseCase(
            staff_repository=self.staff_repo,
            store_repository=StaffStoreAdapter(self.store_repo),
            uniqueness_service=StaffCodeUniquenessService(self.staff_repo),
            assignment_service=StaffStoreAssignmentService(),
            corporate_access=corporate_access,
            account_registration=adapter,
            unit_of_work=NullUnitOfWork(),
            lock=FakeOrganizationLock(),
            clock=FakeClock(datetime(2026, 4, 1, tzinfo=UTC)),
        )


@pytest.mark.asyncio
async def test_tc030_一括登録_正常系() -> None:
    """TC-030: 法人管理者が属性・資格・主所属・accountを一要求で登録し、6種の生成物が同一法人で生成される。"""
    fixture = _Fixture()
    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id)
    await fixture.store_repo.save(store)

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=BulkStaffAccountInput(
            email="staff@example.test",
            password="Password123456789",
            role="store_operator",
        ),
        code="STF-001",
        initial_home_store_id=str(store.id.value),
        initial_start_date=date(2026, 4, 1),
        pharmacist_license_number="123456",
    )

    result = await fixture.use_case.execute(cmd)

    assert isinstance(result, BulkRegisteredStaffResult)
    staff_id = StaffId.parse(result.staff_id)
    person_id = AccountPersonId.parse(result.person_id)
    account_id = UserAccountId.parse(result.account_id)
    membership_id = CorporateMembershipId.parse(result.membership_id)

    # 1. Staff
    staff = await fixture.staff_repo.get(corporate_id=corp_id, staff_id=staff_id)
    assert staff is not None
    assert staff.corporate_id == corp_id
    assert staff.names.kanji.last_name.value == "山田"
    assert staff.current_home_store_id(date(2026, 4, 1)) == store.id
    assert staff.is_pharmacist is True

    # 2. AccountPerson
    person = await fixture.people_repo.get(person_id)
    assert person is not None
    assert person.corporate_id == corp_id

    # 3. StaffPersonLink
    link = await fixture.link_repo.get(staff_id)
    assert link is not None
    assert link.corporate_id == corp_id
    assert link.person_id == person_id

    # 4. UserAccount
    account = await fixture.account_repo.get(account_id)
    assert account is not None
    assert account.corporate_id == corp_id
    assert account.person_id == person_id
    assert account.status == AccountStatus.ACTIVE

    # 5. CorporateMembership
    membership = await fixture.membership_repo.get(membership_id)
    assert membership is not None
    assert membership.corporate_id == corp_id
    assert membership.account_id == account_id
    assert membership.role == MembershipRole.STORE_OPERATOR

    # 6. Credentials
    assert len(fixture.credentials.issued) == 1
    issued_corp, issued_email, _, issued_subject = fixture.credentials.issued[0]
    assert issued_corp == corp_id
    assert issued_email == "staff@example.test"
    assert issued_subject == f"local:{account_id.value}"


@pytest.mark.asyncio
async def test_tc031_一括登録_異常系_パスワードまたはアカウント異常() -> None:
    """TC-031: パスワード等の異常で資格情報保存に失敗した場合、例外が送出される。"""
    fixture = _Fixture()
    corp_id = CorporateId.generate()
    store = create_store(corporate_id=corp_id)
    await fixture.store_repo.save(store)

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=BulkStaffAccountInput(
            email="invalid-email-format",
            password="Short",
            role="store_operator",
        ),
        code="STF-001",
    )

    with pytest.raises(DomainValidationError):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_tc032_共用アカウント_入力異常() -> None:
    """TC-032: アカウント情報のないスタッフ単体登録を拒否する。"""
    fixture = _Fixture()
    corp_id = CorporateId.generate()

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
        account=None,
    )

    with pytest.raises(
        DomainValidationError, match="スタッフ登録にはアカウント情報が必要です"
    ):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_tc033_登録_管理権限_一般利用者と店舗管理者() -> None:
    """TC-033: 一般利用者は403。店舗管理者は自管理店舗の一般利用者のみ許可、範囲外404、管理者権限追加403。"""
    corp_id = CorporateId.generate()
    store1 = create_store(corporate_id=corp_id)
    store2 = create_store(corporate_id=corp_id, name="第二店舗")

    # 1. 一般利用者は403
    general_actor = ResolvedActorContext(
        principal_id="general-user",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=corp_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        store_ids=frozenset({store1.id}),
    )
    fixture_general = _Fixture(actor_context=general_actor)
    await fixture_general.store_repo.save(store1)

    cmd = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="鈴木",
        first_name="次郎",
        last_name_kana="スズキ",
        first_name_kana="ジロウ",
        account=BulkStaffAccountInput(
            email="staff2@example.test",
            password="Password123456789",
            role="store_operator",
        ),
        initial_home_store_id=str(store1.id.value),
    )
    with pytest.raises(AuthorizationError):
        await fixture_general.use_case.execute(cmd)

    # 2. 店舗管理者（管理薬剤師）
    manager_actor = ResolvedActorContext(
        principal_id="manager-user",
        roles=frozenset({ActorRole.STORE_OPERATOR, ActorRole.STORE_MANAGER}),
        corporate_id=corp_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        store_ids=frozenset({store1.id}),
        managed_store_ids=frozenset({store1.id}),
    )
    fixture_manager = _Fixture(actor_context=manager_actor)
    await fixture_manager.store_repo.save(store1)
    await fixture_manager.store_repo.save(store2)

    # 2a. 自管理店舗の一般利用者: 成功
    cmd_ok = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="鈴木",
        first_name="次郎",
        last_name_kana="スズキ",
        first_name_kana="ジロウ",
        account=BulkStaffAccountInput(
            email="staff2@example.test",
            password="Password123456789",
            role="store_operator",
        ),
        initial_home_store_id=str(store1.id.value),
    )
    res = await fixture_manager.use_case.execute(cmd_ok)
    assert res.email == "staff2@example.test"

    # 2b. 管理者権限（corporate_admin）を付与しようとすると 403
    cmd_admin_role = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="田中",
        first_name="三郎",
        last_name_kana="タナカ",
        first_name_kana="サブロウ",
        account=BulkStaffAccountInput(
            email="staff3@example.test",
            password="Password123456789",
            role="corporate_admin",
        ),
        initial_home_store_id=str(store1.id.value),
    )
    with pytest.raises(
        AuthorizationError, match="管理薬剤師は管理者権限を付与できません"
    ):
        await fixture_manager.use_case.execute(cmd_admin_role)

    # 2c. 他店舗（store2）を指定すると 404
    cmd_other_store = RegisterStaffCommand(
        corporate_id=str(corp_id.value),
        last_name="佐藤",
        first_name="四郎",
        last_name_kana="サトウ",
        first_name_kana="シロウ",
        account=BulkStaffAccountInput(
            email="staff4@example.test",
            password="Password123456789",
            role="store_operator",
        ),
        initial_home_store_id=str(store2.id.value),
    )
    with pytest.raises(NotFoundError, match="指定された店舗が見つかりません"):
        await fixture_manager.use_case.execute(cmd_other_store)
