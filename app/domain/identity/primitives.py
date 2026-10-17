"""本人・アカウント・法人アクセス権の識別子。

``AccountPersonId`` と ``UserAccountId`` は Shared Kernel の語彙である。
店舗の状態変更履歴や監査も「誰が操作したか」を残すため、所有コンテキストを
Identity に置くと Store と相互依存になる。利用側は定義元のShared Kernelから直接参照する。
"""

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString


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
    STORE_OPERATOR = "store_operator"
    STORE_VIEWER = "store_viewer"
