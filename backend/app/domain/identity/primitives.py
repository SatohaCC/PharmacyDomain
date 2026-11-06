"""identityの単一値と列挙・検証規則。"""

from __future__ import annotations

import re
from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseEmailAddress,
    BaseNormalizedString,
)


class InvitationStatus(StrEnum):
    """招待の受諾状態。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"


class InvitationDigest(BaseNormalizedString):
    """招待秘密のダイジェスト。"""


class InvitationAddressee(BaseEmailAddress):
    """招待の宛先。本人確認の代用には使わない。"""


class CorporateUserEmail(BaseEmailAddress):
    """法人内アカウントの連絡先メールアドレス。"""


class LoginId(BaseNormalizedString):
    """メールアドレスとは独立したログイン識別子。"""

    def _normalize(self, value: str) -> str:
        return super()._normalize(value).lower()

    def validate(self) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", self.value) is None:
            raise DomainValidationError(
                "ログインIDは先頭を半角英数字とし、半角英数字・ピリオド・ハイフン・下線の3～64文字で指定してください。"
            )


class ExternalSubjectKey(BaseNormalizedString):
    """本人確認基盤で検証済みの発行元を含む一意な主体識別子。"""

    def validate(self) -> None:
        if not self.value or len(self.value) > 1000:
            raise DomainValidationError(
                "外部主体識別子は1から1000文字で指定してください。"
            )


class AccountStatus(StrEnum):
    """個人アカウントの利用状態。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipRole(StrEnum):
    """法人内の固定ロール。"""

    CORPORATE_ADMIN = "corporate_admin"
    MEMBER = "member"


class StoreRole(StrEnum):
    """選択店舗に限って適用する操作権限。"""

    EDITOR = "store_operator"
    VIEWER = "store_viewer"
