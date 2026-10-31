"""操作者を許可する前に取得する、権限を付与していない参照事実。"""

from dataclasses import dataclass
from datetime import date

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import CorporateMembershipId, VendorOperatorId
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
class StaffAffiliationIdentitySnapshot:
    """スタッフ所属期間の参照事実。"""

    store_id: StoreId
    starts_on: date
    ends_on: date | None


@dataclass(frozen=True, kw_only=True)
class StoreIdentitySnapshot:
    """店舗の識別・名称・有効状態の参照事実。"""

    id: StoreId
    corporate_id: CorporateId
    name: str
    code: str | None
    is_active: bool


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
    staff_is_active: bool | None = None
    staff_affiliations: tuple[StaffAffiliationIdentitySnapshot, ...] = ()
    stores: tuple[StoreIdentitySnapshot, ...] = ()


@dataclass(frozen=True, kw_only=True)
class IdentityResolutionSnapshot:
    """外部主体から取得したアカウント・本人・所属の不変な事実。"""

    account_id: UserAccountId | None = None
    account_person_id: AccountPersonId | None = None
    person_id: AccountPersonId | None = None
    operator_id: VendorOperatorId | None = None
    external_subject: ExternalSubjectKey | None = None
    account_status: AccountStatus = AccountStatus.ACTIVE
    is_vendor_admin: bool = False
    membership: MembershipIdentitySnapshot | None = None
