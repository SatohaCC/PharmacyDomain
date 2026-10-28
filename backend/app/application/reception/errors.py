"""Applicationのerrorsを定義する。"""

from __future__ import annotations

from app.application.common.exceptions import ApplicationError


class ReceptionApplicationError(ApplicationError):
    """Receptionユースケースの基底例外。"""

    default_message = "受付処理中にエラーが発生しました。"
    default_code = "RECEPTION_APPLICATION_ERROR"
