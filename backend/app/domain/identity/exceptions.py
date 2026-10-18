"""identityの業務例外。"""

from __future__ import annotations

from app.domain.foundation.exceptions import DomainError


class IdentityConflictError(DomainError):
    """本人・アカウント・法人アクセス権の対応が競合した。"""

    default_message = "本人とアカウントの対応が競合しています。"
    default_code = "IDENTITY_CONFLICT"
