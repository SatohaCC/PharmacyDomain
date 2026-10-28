"""操作者を許可する前に取得する、権限を付与していない参照事実。"""

from dataclasses import dataclass
from datetime import date

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import ManagerAssignmentStatus


@dataclass(frozen=True, kw_only=True)
class ManagerIdentitySnapshot:
    """管理薬剤師の任命の参照事実。権限の有効性はApplicationで判断する。"""

    corporate_id: CorporateId
    store_id: StoreId
    staff_id: StaffId
    person_id: AccountPersonId
    status: ManagerAssignmentStatus
    starts_on: date
    ends_on: date | None


@dataclass(frozen=True, kw_only=True)
class MembershipIdentitySnapshot:
    """法人アクセス権の保存値。利用可能性の判断は含めない。"""

    id: CorporateMembershipId
    account_id: UserAccountId
    corporate_id: CorporateId
    status: AccountStatus
    role: MembershipRole
    staff_id: StaffId | None
    store_ids: frozenset[StoreId]
    suspended_store_ids: frozenset[StoreId] = frozenset()
    manager_assignments: tuple[ManagerIdentitySnapshot, ...] = ()


@dataclass(frozen=True, kw_only=True)
class IdentityResolutionSnapshot:
    """外部主体から取得したアカウント・本人・所属の不変な事実。"""

    account_id: UserAccountId
    account_person_id: AccountPersonId
    person_id: AccountPersonId | None
    external_subject: ExternalSubjectKey | None
    account_status: AccountStatus
    is_vendor_admin: bool
    membership: MembershipIdentitySnapshot | None
