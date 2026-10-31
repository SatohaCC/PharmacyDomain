"""Applicationのlocal_authenticationを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.identity.boundary_models import LoginSession, VerifiedSubject
from app.domain.corporate.identifiers import CorporateId


class CredentialWriter(Protocol):
    """業務登録と同じトランザクションで認証資格情報を保存する。"""

    async def issue(
        self, corporate_id: CorporateId, email: str, password: str, subject: str
    ) -> None:
        """法人内の一意なメールアドレスと初期パスワードを保存し、重複は競合として拒否する。"""
        ...


class LocalAuthentication(Protocol):
    """未認証のログインと、制限付きセッションのパスワード変更。"""

    async def login(self, corporate_id: str, email: str, password: str) -> LoginSession:
        """法人利用者の資格情報を照合し、期限付きセッションを作る。"""
        ...

    async def vendor_login(self, email: str, password: str) -> LoginSession:
        """運営者の資格情報を照合し、期限付きセッションを作る。"""
        ...

    async def authenticate(self, credential: str | None) -> str:
        """変更を完了した有効なセッションだけを業務へ通す。"""
        ...

    async def authenticate_subject(self, credential: str | None) -> VerifiedSubject:
        """有効なセッションから外部主体と選択店舗を取り出す。"""
        ...

    async def select_store(self, token: str, store_id: str) -> LoginSession:
        """選択可能な店舗を固定した新しいセッションを発行する。"""
        ...

    async def change_password(self, token: str, password: str) -> LoginSession:
        """初回変更後、既存セッションを失効して通常セッションを発行する。"""
        ...

    async def logout(self, token: str) -> None:
        """セッションを失効する。"""
        ...
