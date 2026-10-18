"""ローカル認証の入出力と、資格情報を扱う技術境界。"""

from dataclasses import dataclass, field
from typing import Protocol

from app.application.common.exceptions import ApplicationError


class LoginFailedError(ApplicationError):
    """資格情報の不一致と利用不能を同じ応答にする。"""

    default_message = "ログインIDまたはパスワードを確認してください。"
    default_code = "LOGIN_FAILED"


@dataclass(frozen=True, kw_only=True)
class LoginSession:
    """秘密は応答時だけ渡し、通常の文字列表現には含めない。"""

    access_token: str = field(repr=False)
    password_change_required: bool


class CredentialWriter(Protocol):
    """業務登録と同じトランザクションで認証資格情報を保存する。"""

    async def issue(self, login_id: str, password: str, subject: str) -> None:
        """一意なIDと初期パスワードを保存し、重複は競合として拒否する。"""
        ...


class LocalAuthentication(Protocol):
    """未認証のログインと、制限付きセッションのパスワード変更。"""

    async def login(self, login_id: str, password: str) -> LoginSession:
        """資格情報を照合し、期限付きセッションを作る。"""
        ...

    async def authenticate(self, credential: str | None) -> str:
        """変更を完了した有効なセッションだけを業務へ通す。"""
        ...

    async def change_password(self, token: str, password: str) -> LoginSession:
        """初回変更後、既存セッションを失効して通常セッションを発行する。"""
        ...

    async def logout(self, token: str) -> None:
        """セッションを失効する。"""
        ...
