"""Applicationのregister_personを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.commands.dtos.identity_views import PersonDto
from app.application.identity.commands.models import PersonNamesInput
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import AccountPerson
from app.domain.identity.repositories import AccountPersonRepository
from app.domain.shared.actor import AccountPersonId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)


class RegisterPersonUseCase:
    """氏名から同一人物を推測せず、本人を新規に登録する。

    氏名の一致で既存の本人へ寄せると、同姓同名の別人が同じアカウントを共有する。
    既存の本人へ紐付けたい場合は、呼び出し側が本人IDを指定する。
    """

    def __init__(
        self,
        people: AccountPersonRepository,
        access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._people = people
        self._access = access
        self._unit_of_work = unit_of_work

    async def execute(
        self, corporate_id: str | None, names: PersonNamesInput
    ) -> PersonDto:
        """法人を指定しない登録はベンダー専用とする。"""
        self._unit_of_work.ensure_active()
        if corporate_id is None:
            AuthorizationService(self._access.actor).require_vendor_system_admin(
                permission=Permission.REGISTER_CORPORATE
            )
            # ベンダー登録の場合でも、Actorの所属または対象法人が必要
            target_corporate_id = CorporateId.generate()
        else:
            target_corporate_id = CorporateId.parse(corporate_id)
            await self._access.require_active(
                corporate_id=target_corporate_id,
                permission=Permission.MANAGE_STAFF,
            )
        person = AccountPerson(
            id=AccountPersonId.generate(),
            corporate_id=target_corporate_id,
            names=PersonNames(
                kanji=PersonName(
                    last_name=PersonNamePart(names.last_name),
                    first_name=PersonNamePart(names.first_name),
                ),
                kana=PersonNameKana(
                    last_name=PersonNameKanaPart(names.last_name_kana),
                    first_name=PersonNameKanaPart(names.first_name_kana),
                ),
            ),
        )
        await self._people.save(person)
        return PersonDto.from_entity(person)
