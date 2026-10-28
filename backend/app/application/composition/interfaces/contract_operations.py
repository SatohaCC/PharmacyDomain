"""法人契約の一括登録が要求する操作契約。"""

from __future__ import annotations

from typing import Protocol

from app.application.corporate.commands.models import RegisterCorporateCommand
from app.application.identity.commands.dtos.identity_views import PersonDto
from app.application.identity.commands.dtos.registration_results import (
    RegisteredLocalUser,
)
from app.application.identity.commands.models import (
    PersonNamesInput,
    RegisterLocalUserCommand,
)
from app.domain.corporate.identifiers import CorporateId


class RegisterCorporateOperation(Protocol):
    async def execute(self, command: RegisterCorporateCommand) -> CorporateId:
        """認可・検証を伴う登録操作を実行する。"""
        ...


class RegisterLocalUserOperation(Protocol):
    async def execute(self, command: RegisterLocalUserCommand) -> RegisteredLocalUser:
        """認可・検証を伴う登録操作を実行する。"""
        ...


class RegisterPersonOperation(Protocol):
    async def execute(
        self, corporate_id: str | None, names: PersonNamesInput
    ) -> PersonDto:
        """認可・検証を伴う登録操作を実行する。"""
        ...
