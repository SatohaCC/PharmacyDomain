"""退職に伴うアクセス権の失効と、在任中の任命との関係を確認する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.composition.staff_integrity import StaffAssignmentWriteGuard
from app.application.staff.deactivate_staff import (
    DeactivateStaffCommand,
    DeactivateStaffUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    AccountStatus,
    CorporateMembershipId,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.manager_repository import ManagerAssignmentConflictError
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.staff.access_revocation_helpers import create_access_revocation
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_identity_repositories import (
    InMemoryCorporateMembershipRepository,
    InMemoryUserAccountRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

_TODAY = date(2026, 9, 17)
_NOW = datetime(2026, 9, 17, 3, tzinfo=UTC)


@pytest.mark.asyncio
async def test_退職は法人アクセス権を停止し再雇用では権限を復活させない() -> None:
    # Arrange
    staffs = InMemoryStaffRepository()
    staff = create_staff()
    await staffs.save(staff)
    accounts = InMemoryUserAccountRepository()
    account = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
    )
    await accounts.save(account)
    memberships = InMemoryCorporateMembershipRepository()
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=staff.corporate_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
        staff_id=staff.id,
    )
    await memberships.save(membership)
    use_case = DeactivateStaffUseCase(
        repository=staffs,
        corporate_access=create_vendor_corporate_access(),
        access_revocation=create_access_revocation(memberships, accounts),
    )

    # Act
    await use_case.execute(
        DeactivateStaffCommand(
            corporate_id=str(staff.corporate_id.value),
            staff_id=str(staff.id.value),
            retired_on=_TODAY,
        )
    )

    # Assert: 法人アクセス権だけが止まり、個人アカウントは残る。
    revoked = await memberships.get(membership.id)
    assert revoked is not None and revoked.status == AccountStatus.SUSPENDED
    unchanged = await accounts.get(account.id)
    assert unchanged is not None and unchanged.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_有効なスタッフの保存では_アクセス権を止めない() -> None:
    """再雇用で権限が復活しないのと同じく、通常の更新でも止めない。"""
    # Arrange
    accounts = InMemoryUserAccountRepository()
    memberships = InMemoryCorporateMembershipRepository()
    staff = create_staff()
    account = UserAccount(
        id=UserAccountId.generate(), person_id=AccountPersonId.generate()
    )
    await accounts.save(account)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=staff.corporate_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset(),
        staff_id=staff.id,
    )
    await memberships.save(membership)

    # Act
    await create_access_revocation(memberships, accounts).revoke_for(staff)

    # Assert
    actual = await memberships.get(membership.id)
    assert actual is not None and actual.status == AccountStatus.ACTIVE


async def _guard_with(
    *, assignment_end: date | None
) -> tuple[StaffAssignmentWriteGuard, Staff]:
    """指定した終了日の任命を1件持つ、管理薬剤師のスタッフを用意する。"""
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)
    staff = replace(
        create_staff(
            corporate_id=store.corporate_id,
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
    managers = InMemoryStoreManagerAssignmentRepository()
    await managers.save(
        StoreManagerAssignment(
            id=StoreManagerAssignmentId.generate(),
            corporate_id=store.corporate_id,
            store_id=store.id,
            staff_id=staff.id,
            period=ManagerAssignmentPeriod(
                starts_on=date(2026, 1, 1), ends_on=assignment_end
            ),
        )
    )
    guard = StaffAssignmentWriteGuard(
        stores, managers, FakeClock(_NOW), FakeOrganizationLock()
    )
    return guard, staff


@pytest.mark.asyncio
async def test_任命を今日で終了したスタッフは_同じ日に退職できる() -> None:
    """終了日は含む閉区間なので、最終日まで務めた任命と当日の退職は両立する。

    終了日当日の任命を在任中として検証していた頃は、無効化済みのスタッフが
    管理薬剤師の要件を満たさないと判定され、翌日まで退職できなかった。
    """
    # Arrange
    guard, staff = await _guard_with(assignment_end=_TODAY)

    # Act & Assert: 例外が出ない。
    await guard.check(staff.deactivate(_TODAY), False)


@pytest.mark.asyncio
async def test_在任中の任命が残るスタッフは_退職できない() -> None:
    """先に任命を終了させないと、管理薬剤師のいない店舗ができる。"""
    # Arrange
    guard, staff = await _guard_with(assignment_end=None)

    # Act & Assert
    with pytest.raises(ManagerAssignmentConflictError):
        await guard.check(staff.deactivate(_TODAY), False)


@pytest.mark.asyncio
async def test_明日まで続く任命が残るスタッフは_退職できない() -> None:
    """境界の緩和が「終了日以前」に留まっていることを確かめる。"""
    # Arrange
    guard, staff = await _guard_with(assignment_end=date(2026, 9, 18))

    # Act & Assert
    with pytest.raises(ManagerAssignmentConflictError):
        await guard.check(staff.deactivate(_TODAY), False)


class _事象記録:
    """ロック取得と任命の読み出しの順序を1本の列に残す。"""

    def __init__(self) -> None:
        self.events: list[str] = []


class _記録ロック(FakeOrganizationLock):
    """取得したキーを共有の記録へ流す。"""

    def __init__(self, log: _事象記録) -> None:
        super().__init__()
        self._log = log

    async def acquire(self, key: str) -> None:
        await super().acquire(key)
        self._log.events.append(f"lock:{key}")


class _記録任命保存(InMemoryStoreManagerAssignmentRepository):
    """スタッフ単位の読み出しを共有の記録へ流す。"""

    def __init__(self, log: _事象記録) -> None:
        super().__init__()
        self._log = log

    async def list_by_staff(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> list[StoreManagerAssignment]:
        self._log.events.append("read:assignments")
        return await super().list_by_staff(corporate_id, staff_id)


@pytest.mark.asyncio
async def test_スタッフ保存前の検証は_法人ロックを取ってから任命を読む() -> None:
    """読み出しがロックの外に出ると、任命との競合が両方成功する。

    任命を書く側は実行の冒頭で同じキーを取る。ここで取らないと、資格を外す保存と
    任命の登録が互いの確定前を読み、例外なしで「管理薬剤師でないスタッフの
    在任中の任命」が残る。実DBを使わずに、読み出しがロックの内側にあることだけを
    固定する。
    """
    # Arrange
    log = _事象記録()
    store = create_store()
    stores = InMemoryStoreRepository()
    await stores.save(store)
    staff = create_staff(corporate_id=store.corporate_id)
    guard = StaffAssignmentWriteGuard(
        stores, _記録任命保存(log), FakeClock(_NOW), _記録ロック(log)
    )

    # Act
    await guard.check(staff, False)

    # Assert
    assert log.events == [
        f"lock:corporate:{store.corporate_id.value}",
        "read:assignments",
    ]


@pytest.mark.asyncio
async def test_スタッフ以外の保存では_法人ロックを取らない() -> None:
    """ロックの対象をスタッフの保存に限る。集約を問わず取ると、全ての書き込みが
    法人単位で直列化する（以前 ``get()`` でロックを取っていたときと同じ害）。
    """
    # Arrange
    log = _事象記録()
    guard = StaffAssignmentWriteGuard(
        InMemoryStoreRepository(), _記録任命保存(log), FakeClock(_NOW), _記録ロック(log)
    )

    # Act
    await guard.check(create_store(), True)

    # Assert
    assert log.events == []
