"""本人管理の外部入力。Domainの型をHTTPへ再公開しない。"""

from dataclasses import dataclass
from enum import StrEnum


class AccountStatus(StrEnum):
    """アクセス権変更で指定できる状態。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipRole(StrEnum):
    """招待や権限変更で指定できる法人内ロール。"""

    CORPORATE_ADMIN = "corporate_admin"
    STORE_OPERATOR = "store_operator"
    STORE_VIEWER = "store_viewer"


@dataclass(frozen=True, kw_only=True)
class PersonNamesInput:
    """本人登録時に受け取る氏名の文字列。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
