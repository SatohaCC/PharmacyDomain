"""Applicationのdtoを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.optional_conversion import optional_id
from app.domain.identity.entities import (
    CorporateMembership,
    UserAccount,
)
from app.domain.identity.primitives import (
    AccountStatus,
    MembershipRole,
)


@dataclass(frozen=True)
class MembershipViewDto:
    """法人の利用者一覧・詳細で返す値。

    法人アクセス権の状態と、その土台にある個人アカウントの状態は別物である。
    片方だけを返すと「権限は有効だがアカウントが停止中」という組み合わせを
    呼び出し側が区別できない。外部主体識別子は含めない。
    """

    id: str
    account_id: str
    person_id: str
    corporate_id: str
    status: AccountStatus
    account_status: AccountStatus
    role: MembershipRole
    store_ids: tuple[str, ...]
    staff_id: str | None
    suspended_store_ids: tuple[str, ...] = ()

    @classmethod
    def from_entities(
        cls, membership: CorporateMembership, account: UserAccount
    ) -> MembershipViewDto:
        """権限とアカウントの状態を1つの公開値へまとめる。"""
        return cls(
            str(membership.id.value),
            str(account.id.value),
            str(account.person_id.value),
            str(membership.corporate_id.value),
            membership.status,
            account.status,
            membership.role,
            tuple(
                str(item.value)
                for item in sorted(membership.store_ids, key=lambda item: item.value)
            ),
            optional_id(membership.staff_id),
            tuple(
                str(item.value)
                for item in sorted(
                    membership.suspended_store_ids, key=lambda item: item.value
                )
            ),
        )


@dataclass(frozen=True, kw_only=True)
class SelectableStoreDto:
    """現在選択可能な店舗の表示値。"""

    id: str
    name: str
    code: str | None = None
