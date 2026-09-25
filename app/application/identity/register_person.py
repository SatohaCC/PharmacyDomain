"""本人記録の新規作成ユースケース。"""

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.policy import AuthorizationService
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.dto import PersonDto
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.primitives import AccountPersonId
from app.domain.identity.repository import AccountPersonRepository
from app.domain.shared.person_name import PersonNames


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

    async def execute(self, corporate_id: str | None, names: PersonNames) -> PersonDto:
        """法人を指定しない登録はベンダー専用とする。"""
        self._unit_of_work.ensure_active()
        if corporate_id is None:
            AuthorizationService(self._access.actor).require_vendor_system_admin(
                permission=Permission.REGISTER_CORPORATE
            )
        else:
            await self._access.require_active(
                corporate_id=CorporateId.parse(corporate_id),
                permission=Permission.MANAGE_STAFF,
            )
        person = AccountPerson(id=AccountPersonId.generate(), names=names)
        await self._people.save(person)
        return PersonDto.from_entity(person)


__all__ = ["RegisterPersonUseCase"]
