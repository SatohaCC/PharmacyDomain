"""スタッフ・アカウント一括登録（TC-030〜TC-033）のApplication層テスト。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
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
    staff_store_source,
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
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.staff.value_objects import PharmacistProfile, StaffQualifications
from app.domain.store.entities import Store
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.factories.identity_factory import (
    create_account_person,
    create_corporate_membership,
    create_staff_person_link,
    create_user_account,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    FakeCredentialWriter,
    InMemoryAccountPersonRepository,
    InMemoryCorporateMembershipRepository,
    InMemoryStaffPersonLinkRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


class _RegistrationLock(FakeOrganizationLock):
    """法人ロック取得時点で競合更新を反映する。"""

    def __init__(self) -> None:
        super().__init__()
        self.on_corporate_lock: Callable[[], Awaitable[None]] | None = None

    async def acquire(self, key: str) -> None:
        await super().acquire(key)
        if key.startswith("corporate:") and self.on_corporate_lock is not None:
            await self.on_corporate_lock()


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
        self.managers = InMemoryStoreManagerAssignmentRepository()
        self.lock = _RegistrationLock()

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
            lock=self.lock,
            clock=FakeClock(datetime(2026, 4, 1, tzinfo=UTC)),
            store_managers=self.managers,
        )

    async def seed_manager(self, actor: ResolvedActorContext, store: Store) -> None:
        """解決済みActorに対応する現在の任命・本人・利用権限を保存する。"""
        assert (
            actor.staff_id is not None
            and actor.account_id is not None
            and actor.person_id is not None
            and actor.membership_id is not None
        )
        staff = replace(
            create_staff(
                corporate_id=store.corporate_id,
                qualifications=StaffQualifications.from_profiles(
                    PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
                ),
            ),
            id=actor.staff_id,
        )
        staff = StaffStoreAssignmentService().assign_home_store(
            staff, staff_store_source(store), date(2026, 1, 1)
        )
        await self.staff_repo.save(staff)
        await self.people_repo.save(
            create_account_person(
                corporate_id=store.corporate_id, person_id=actor.person_id
            )
        )
        await self.account_repo.save(
            create_user_account(
                corporate_id=store.corporate_id,
                account_id=actor.account_id,
                person_id=actor.person_id,
            )
        )
        await self.membership_repo.save(
            create_corporate_membership(
                corporate_id=store.corporate_id,
                account_id=actor.account_id,
                membership_id=actor.membership_id,
                staff_id=actor.staff_id,
                store_ids=frozenset({store.id}),
            )
        )
        await self.link_repo.save(
            create_staff_person_link(
                corporate_id=store.corporate_id,
                staff_id=actor.staff_id,
                person_id=actor.person_id,
            )
        )
        await self.managers.save(
            create_manager_assignment(
                corporate_id=store.corporate_id,
                store_id=store.id,
                staff_id=actor.staff_id,
                person_id=actor.person_id,
            )
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
        staff_id=StaffId.generate(),
        membership_id=CorporateMembershipId.generate(),
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
    await fixture_manager.seed_manager(manager_actor, store1)

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "appointment",
        "account",
        "membership",
        "person",
        "staff",
        "store_access",
        "link",
        "staff_scope",
    ],
)
async def test_スタッフ一括登録_法人ロック待機中に管理者状態が失効_生成前に拒否する(
    change: str,
) -> None:
    # Arrange
    corporate = CorporateId.generate()
    store = create_store(corporate_id=corporate)
    actor = ResolvedActorContext(
        principal_id="テスト管理薬剤師",
        roles=frozenset({ActorRole.STORE_OPERATOR, ActorRole.STORE_MANAGER}),
        corporate_id=corporate,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        membership_id=CorporateMembershipId.generate(),
        staff_id=StaffId.generate(),
        store_ids=frozenset({store.id}),
        managed_store_ids=frozenset({store.id}),
    )
    fixture = _Fixture(actor_context=actor)
    await fixture.store_repo.save(store)
    await fixture.seed_manager(actor, store)

    async def invalidate() -> None:
        if change == "appointment":
            fixture.managers.items.clear()
        elif change == "account":
            assert actor.account_id is not None
            account = await fixture.account_repo.get(actor.account_id)
            assert account is not None
            await fixture.account_repo.save(account.suspend())
        elif change == "membership":
            assert actor.membership_id is not None
            membership = await fixture.membership_repo.get(actor.membership_id)
            assert membership is not None
            await fixture.membership_repo.save(
                replace(membership, status=AccountStatus.SUSPENDED)
            )
        elif change == "person":
            assignment = next(iter(fixture.managers.items.values()))
            await fixture.managers.save(
                replace(assignment, person_id=AccountPersonId.generate())
            )
        elif change == "store_access":
            assert actor.membership_id is not None
            membership = await fixture.membership_repo.get(actor.membership_id)
            assert membership is not None
            await fixture.membership_repo.save(
                replace(membership, store_ids=frozenset())
            )
        elif change == "link":
            assert actor.staff_id is not None
            fixture.link_repo.items.pop(actor.staff_id)
        else:
            assert actor.staff_id is not None
            staff = await fixture.staff_repo.get(
                corporate_id=corporate, staff_id=actor.staff_id
            )
            assert staff is not None
            if change == "staff_scope":
                other_store = create_store(corporate_id=corporate)
                staff = StaffStoreAssignmentService().transfer_home_store(
                    staff, staff_store_source(other_store), date(2026, 4, 1)
                )
            else:
                staff = replace(staff, is_active=False)
            await fixture.staff_repo.save(staff)

    fixture.lock.on_corporate_lock = invalidate
    command = RegisterStaffCommand(
        corporate_id=str(corporate.value),
        last_name="テスト",
        first_name="太郎",
        last_name_kana="テスト",
        first_name_kana="タロウ",
        initial_home_store_id=str(store.id.value),
        initial_start_date=date(2026, 4, 1),
        account=BulkStaffAccountInput(
            email="test-user@example.test", password="test-password-12345"
        ),
    )
    # Act / Assert
    with pytest.raises(AuthorizationError):
        await fixture.use_case.execute(command)
    assert fixture.lock.keys == ["identity", f"corporate:{corporate.value}"]
    assert len(await fixture.staff_repo.list_all()) == 1
    assert fixture.credentials.issued == []
