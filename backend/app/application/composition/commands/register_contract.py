"""Applicationのregister_contractを定義する。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.common.unit_of_work import UnitOfWork
from app.application.composition.interfaces.contract_operations import (
    RegisterContractAdminOperation,
    RegisterCorporateOperation,
    RegisterPersonOperation,
)
from app.application.corporate.commands.models import RegisterCorporateCommand
from app.application.identity.commands.models import PersonNamesInput


@dataclass(frozen=True, kw_only=True)
class RegisterContractCommand:
    """法人基本情報と初期管理者の登録入力。"""

    name: str
    representative_last_name: str
    representative_first_name: str
    administrator: PersonNamesInput
    email: str
    initial_password: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class RegisteredContract:
    """登録を完了した契約の識別子。"""

    id: str
    account_id: str
    email: str


class RegisterContractUseCase:
    """法人だけ、または管理者だけが保存される部分登録を防ぐ。"""

    def __init__(
        self,
        corporate: RegisterCorporateOperation,
        person: RegisterPersonOperation,
        admin_user: RegisterContractAdminOperation,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._corporate = corporate
        self._person = person
        self._admin_user = admin_user
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterContractCommand) -> RegisteredContract:
        """法人登録のベンダー認可から始め、全件が成功した場合だけ確定する。"""
        self._unit_of_work.ensure_active()
        corporate_id = await self._corporate.execute(
            RegisterCorporateCommand(
                name=command.name,
                representative_last_name=command.representative_last_name,
                representative_first_name=command.representative_first_name,
            )
        )
        identifier = str(corporate_id.value)
        person = await self._person.execute(identifier, command.administrator)
        user = await self._admin_user.execute(
            corporate_id=identifier,
            person_id=str(person.id.value),
            email=command.email,
            initial_password=command.initial_password,
        )
        return RegisteredContract(id=identifier, account_id=user.id, email=user.email)
