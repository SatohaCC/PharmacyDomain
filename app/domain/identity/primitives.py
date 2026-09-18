"""本人・アカウント・法人アクセス権の識別子。"""

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString, EntityUUID


class ExternalSubjectKey(BaseNormalizedString):
    """本人確認基盤で検証済みの発行元を含む一意な主体識別子。"""

    def validate(self) -> None:
        if not self.value or len(self.value) > 1000:
            raise DomainValidationError(
                "外部主体識別子は1から1000文字で指定してください。"
            )


class AccountPersonId(EntityUUID):
    """操作する人の識別子。"""

    identifier_name = "本人ID"


class UserAccountId(EntityUUID):
    """個人アカウントの識別子。"""

    identifier_name = "アカウントID"


class CorporateMembershipId(EntityUUID):
    """法人アクセス権の識別子。"""

    identifier_name = "法人アクセス権ID"


class UserInvitationId(EntityUUID):
    """本人を指定した招待の識別子。"""

    identifier_name = "招待ID"


class AccountStatus(StrEnum):
    """個人アカウントの利用状態。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipRole(StrEnum):
    """法人内の固定ロール。"""

    CORPORATE_ADMIN = "corporate_admin"
    STORE_OPERATOR = "store_operator"
    STORE_VIEWER = "store_viewer"
