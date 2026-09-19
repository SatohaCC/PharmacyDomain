"""アカウント状態を含めて最後の法人管理者を保護する。"""

from collections.abc import Sequence

from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.identity.user_account import UserAccount


class LastAdministratorService:
    """変更前後の実効的な管理者を比較する無状態の規則。"""

    def ensure_preserved(
        self,
        *,
        corporate_id: CorporateId,
        previous_memberships: Sequence[CorporateMembership],
        previous_accounts: Sequence[UserAccount],
        updated_memberships: Sequence[CorporateMembership],
        updated_accounts: Sequence[UserAccount],
    ) -> None:
        """管理者のいた法人が変更後に管理者不在になる操作を拒否する。"""

        def has_administrator(
            memberships: Sequence[CorporateMembership], accounts: Sequence[UserAccount]
        ) -> bool:
            active_accounts = {
                account.id
                for account in accounts
                if account.status == AccountStatus.ACTIVE
            }
            return any(
                membership.corporate_id == corporate_id
                and membership.status == AccountStatus.ACTIVE
                and membership.role == MembershipRole.CORPORATE_ADMIN
                and membership.account_id in active_accounts
                for membership in memberships
            )

        if has_administrator(
            previous_memberships, previous_accounts
        ) and not has_administrator(updated_memberships, updated_accounts):
            raise IdentityConflictError(
                "最後の有効な法人管理者を失う変更はできません。"
            )
