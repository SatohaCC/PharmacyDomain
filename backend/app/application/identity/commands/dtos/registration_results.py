"""利用者登録の更新結果を表す。"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class IssuedInvitation:
    """発行時だけ返す招待秘密。"""

    id: str
    secret: str


@dataclass(frozen=True, kw_only=True)
class RegisteredLocalUser:
    """登録完了したアカウント。パスワードは再表示しない。"""

    id: str
    login_id: str
