"""本人とアカウントの整合性違反。"""

from app.domain.foundation.exceptions import DomainError


class IdentityConflictError(DomainError):
    """本人・アカウント・法人アクセス権の対応が競合した。"""

    default_message = "本人とアカウントの対応が競合しています。"
    default_code = "IDENTITY_CONFLICT"
