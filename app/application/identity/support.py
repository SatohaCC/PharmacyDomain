"""Identityの複数ユースケースが共有する保存境界と検証。"""

from dataclasses import dataclass

from app.application.common.exceptions import NotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.administrator_service import LastAdministratorService
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    MembershipRole,
)
from app.domain.identity.repository import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    StaffPersonLinkRepository,
    UserAccountRepository,
    UserInvitationRepository,
)
from app.domain.identity.user_account import UserAccount
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True)
class IdentityRepositories:
    """同じUoWに接続されたIdentityの保存境界。"""

    people: AccountPersonRepository
    accounts: UserAccountRepository
    memberships: CorporateMembershipRepository
    links: StaffPersonLinkRepository
    invitations: UserInvitationRepository


async def validate_membership_target(
    *,
    person_id: AccountPersonId,
    corporate_id: CorporateId,
    role: MembershipRole,
    store_ids: frozenset[StoreId],
    staff_id: StaffId | None,
    staff: StaffRepository,
    stores: StoreRepository,
    links: StaffPersonLinkRepository,
) -> None:
    """権限を与える先の本人・Staff・許可店舗が、その法人のものか確かめる。

    招待の発行と、既存アクセス権の有効化・変更の両方で必要になる。片方にだけ
    書くと、招待では拒まれる組み合わせを権限変更では作れてしまう。

    Raises:
        DomainValidationError: 店舗ロールにスタッフ参照が無い場合。
        NotFoundError: 指定された店舗またはスタッフが対象法人に無い場合。
        IdentityConflictError: 本人とスタッフの対応が無い、または退職済みの場合。
    """
    if role != MembershipRole.CORPORATE_ADMIN and staff_id is None:
        raise DomainValidationError("店舗ロールにはスタッフ参照が必要です。")
    for store_id in store_ids:
        store = await stores.get(store_id)
        if store is None or store.corporate_id != corporate_id:
            raise NotFoundError("指定された店舗が見つかりません。")
    if staff_id is None:
        return
    member = await staff.get(corporate_id=corporate_id, staff_id=staff_id)
    if member is None or member.corporate_id != corporate_id:
        raise NotFoundError("指定されたスタッフが見つかりません。")
    link = await links.get(staff_id)
    if (
        link is None
        or link.person_id != person_id
        or link.corporate_id != corporate_id
        or not member.is_active
    ):
        raise IdentityConflictError("有効な本人とスタッフの対応が必要です。")


async def ensure_administrator_preserved(
    corporate_id: CorporateId,
    *,
    memberships: CorporateMembershipRepository,
    accounts: UserAccountRepository,
    updated_membership: CorporateMembership | None = None,
    updated_account: UserAccount | None = None,
) -> None:
    """変更前後の実効管理者を比べ、管理者不在になる操作を拒否する。

    呼び出し側はこれをロックの内側で使う。ロックの外だと、2人の管理者が同時に
    停止して両方の判定が「もう1人いる」を見る。
    """
    before = await memberships.list_by_corporate(corporate_id)
    known = await accounts.list_by_ids({item.account_id for item in before})
    LastAdministratorService().ensure_preserved(
        corporate_id=corporate_id,
        previous_memberships=before,
        previous_accounts=known,
        updated_memberships=[
            updated_membership
            if updated_membership is not None and item.id == updated_membership.id
            else item
            for item in before
        ],
        updated_accounts=[
            updated_account
            if updated_account is not None and item.id == updated_account.id
            else item
            for item in known
        ],
    )


__all__ = [
    "IdentityRepositories",
    "ensure_administrator_preserved",
    "validate_membership_target",
]
