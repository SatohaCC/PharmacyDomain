"""Applicationのregister_staff_for_adminを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.exceptions import NotFoundError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.identity.commands.services.repositories import IdentityRepositories
from app.application.identity.interfaces.staff_creator import StaffCreationBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import StaffPersonLink
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.identifiers import StaffId


@dataclass(frozen=True, kw_only=True)
class RegisterStaffForAdminCommand:
    """初期管理者へのスタッフ登録入力。"""

    corporate_id: str
    membership_id: str
    last_name: str | None = None
    first_name: str | None = None
    last_name_kana: str | None = None
    first_name_kana: str | None = None
    code: str | None = None
    job_title: str | None = None
    phone_number: str | None = None
    email: str | None = None
    initial_home_store_id: str | None = None
    initial_start_date: date | None = None
    pharmacist_license_number: str | None = None
    insurance_pharmacist_registration_number: str | None = None
    insurance_pharmacist_registration_date: date | None = None
    registered_seller_number: str | None = None
    dietitian_registration_number: str | None = None
    is_registered_dietitian: bool = True


class RegisterStaffForAdminUseCase:
    """スタッフ未紐付けの管理者メンバーシップにスタッフとリンクを紐付ける。"""

    def __init__(
        self,
        repositories: IdentityRepositories,
        corporate_access: CorporateAccessBoundary,
        staff_creator: StaffCreationBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
    ) -> None:
        self._repositories = repositories
        self._corporate_access = corporate_access
        self._staff_creator = staff_creator
        self._unit_of_work = unit_of_work
        self._lock = lock

    async def execute(self, command: RegisterStaffForAdminCommand) -> StaffId:
        """初期管理者にスタッフを生成・紐付け、スタッフIDを返す。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
        )
        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")

        membership = await self._repositories.memberships.get(
            CorporateMembershipId.parse(command.membership_id)
        )
        if membership is None or membership.corporate_id != corporate_id:
            raise NotFoundError("指定されたメンバーシップが見つかりません。")
        if membership.staff_id is not None:
            raise IdentityConflictError(
                "このメンバーシップには既にスタッフが登録されています。"
            )

        account = await self._repositories.accounts.get(membership.account_id)
        if account is None or account.corporate_id != corporate_id:
            raise NotFoundError("指定されたアカウントが見つかりません。")

        person = await self._repositories.people.get(account.person_id)
        if person is None or person.corporate_id != corporate_id:
            raise NotFoundError("指定された本人が見つかりません。")

        if (
            command.last_name
            and command.first_name
            and command.last_name_kana
            and command.first_name_kana
        ):
            names = PersonNames(
                kanji=PersonName(
                    last_name=PersonNamePart(command.last_name),
                    first_name=PersonNamePart(command.first_name),
                ),
                kana=PersonNameKana(
                    last_name=PersonNameKanaPart(command.last_name_kana),
                    first_name=PersonNameKanaPart(command.first_name_kana),
                ),
            )
        else:
            names = person.names

        staff_id = await self._staff_creator.create_staff(
            corporate_id=corporate_id,
            names=names,
            code=command.code,
            job_title=command.job_title,
            phone_number=command.phone_number,
            email=command.email,
            initial_home_store_id=command.initial_home_store_id,
            initial_start_date=command.initial_start_date,
            pharmacist_license_number=command.pharmacist_license_number,
            insurance_pharmacist_registration_number=command.insurance_pharmacist_registration_number,
            insurance_pharmacist_registration_date=command.insurance_pharmacist_registration_date,
            registered_seller_number=command.registered_seller_number,
            dietitian_registration_number=command.dietitian_registration_number,
            is_registered_dietitian=command.is_registered_dietitian,
        )

        link = StaffPersonLink(
            id=staff_id,
            corporate_id=corporate_id,
            person_id=person.id,
        )
        await self._repositories.links.save(link)

        updated_membership = membership.assign_staff(staff_id)
        await self._repositories.memberships.save(updated_membership)

        return staff_id
