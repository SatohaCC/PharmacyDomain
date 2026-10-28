"""Applicationのlocal_authenticationを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.identity.boundary_models import LoginSession


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
