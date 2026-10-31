"""法人契約の一括登録が要求する操作契約。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.corporate.commands.models import RegisterCorporateCommand
from app.application.identity.commands.dtos.identity_views import PersonDto
from app.application.identity.commands.models import PersonNamesInput
from app.domain.corporate.identifiers import CorporateId


@dataclass(frozen=True, kw_only=True)
class RegisteredAdminUser:
    """登録完了した管理者アカウント。"""

    id: str
    email: str


class RegisterCorporateOperation(Protocol):
    async def execute(self, command: RegisterCorporateCommand) -> CorporateId:
        """認可・検証を伴う登録操作を実行する。"""
        ...


class RegisterPersonOperation(Protocol):
    async def execute(
        self, corporate_id: str | None, names: PersonNamesInput
    ) -> PersonDto:
        """認可・検証を伴う登録操作を実行する。"""
        ...


class RegisterContractAdminOperation(Protocol):
    async def execute(
        self,
        *,
        corporate_id: str,
        person_id: str,
        email: str,
        initial_password: str,
    ) -> RegisteredAdminUser:
        """初期管理者のアカウントと認証資格情報を保存する。"""
        ...
