"""Applicationのerrorsを定義する。"""

from __future__ import annotations

from app.application.common.exceptions import ApplicationError


class LoginFailedError(ApplicationError):
    """資格情報の不一致と利用不能を同じ応答にする。"""

    default_message = "ログインIDまたはパスワードを確認してください。"
    default_code = "LOGIN_FAILED"


class UnavailableIdentityError(ApplicationError):
    """本人またはアカウントを利用可能な状態として解決できない。"""

    default_message = "この本人のアカウントは利用できません。"
