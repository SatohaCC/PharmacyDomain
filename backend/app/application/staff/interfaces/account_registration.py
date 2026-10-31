"""スタッフ作成時の一括アカウント生成境界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class StaffAccountRegistrationResult:
    """スタッフと同時に生成されたアカウント群の識別子。"""

    person_id: AccountPersonId
    account_id: UserAccountId
    membership_id: CorporateMembershipId
    email: str


class StaffAccountRegistrationBoundary(Protocol):
    """スタッフ登録と同じUoW内で本人・アカウント・所属・資格情報を生成する。"""

    async def register_account(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        names: PersonNames,
        email: str,
        password: str,
        role: str,
        store_ids: frozenset[StoreId],
    ) -> StaffAccountRegistrationResult:
        """アカウントと資格情報を保存し、生成された識別子を返す。"""
        ...
