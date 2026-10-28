"""Applicationのregister_contractを定義する。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.common.unit_of_work import UnitOfWork
from app.application.composition.interfaces.contract_operations import (
    RegisterCorporateOperation,
    RegisterLocalUserOperation,
    RegisterPersonOperation,
)
from app.application.corporate.commands.models import RegisterCorporateCommand
from app.application.identity.commands.models import (
    PersonNamesInput,
    RegisterLocalUserCommand,
)


@dataclass(frozen=True, kw_only=True)
class RegisterContractCommand:
    """法人基本情報と初期管理者の登録入力。"""

    name: str
    representative_last_name: str
    representative_first_name: str
    administrator: PersonNamesInput
    login_id: str
    initial_password: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class RegisteredContract:
    """登録を完了した契約の識別子。"""

    id: str
    account_id: str
    login_id: str


class RegisterContractUseCase:
    """法人だけ、または管理者だけが保存される部分登録を防ぐ。"""

    def __init__(
        self,
        corporate: RegisterCorporateOperation,
        person: RegisterPersonOperation,
        user: RegisterLocalUserOperation,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._corporate = corporate
        self._person = person
        self._user = user
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
        user = await self._user.execute(
            RegisterLocalUserCommand(
                corporate_id=identifier,
                person_id=str(person.id.value),
                login_id=command.login_id,
                initial_password=command.initial_password,
            )
        )
        return RegisteredContract(
            id=identifier, account_id=user.id, login_id=user.login_id
        )
