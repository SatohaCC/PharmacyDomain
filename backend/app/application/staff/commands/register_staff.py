"""Applicationのregister_staffを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.common.input_normalization import to_optional_text
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.staff.commands.services.support import load_store_or_raise
from app.application.staff.interfaces.account_registration import (
    StaffAccountRegistrationBoundary,
)
from app.application.staff.interfaces.references import StaffStoreReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import (
    DietitianRegistrationNumber,
    EmploymentType,
    InsurancePharmacistRegistrationNumber,
    JobTitle,
    PharmacistLicenseNumber,
    SellerRegistrationNumber,
    StaffCode,
    StaffEmailAddress,
    StaffPhoneNumber,
    WeeklyContractHours,
)
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.services import (
    StaffCodeUniquenessService,
    StaffStoreAssignmentService,
)
from app.domain.staff.value_objects import (
    BaseQualificationProfile,
    DietitianProfile,
    InsurancePharmacistRegistration,
    PharmacistProfile,
    RegisteredSellerProfile,
    StaffQualifications,
)
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreManagerAssignmentRepository


@dataclass(frozen=True, kw_only=True)
class BulkStaffAccountInput:
    """スタッフと同時に生成するアカウントの入力情報。"""

    email: str
    password: str
    role: str = "store_operator"
    store_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, kw_only=True)
class RegisterStaffCommand:
    """スタッフ新規登録に必要な入力データ（DTO）。"""

    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    account: BulkStaffAccountInput | None = None
    job_title: str | None = None
    code: str | None = None
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
    employment_type: str = "regular"
    weekly_contract_hours: float | None = None


@dataclass(frozen=True, kw_only=True)
class BulkRegisteredStaffResult:
    """一括登録結果。"""

    staff_id: str
    person_id: str
    account_id: str
    membership_id: str
    email: str


class RegisterStaffUseCase:
    """スタッフおよびアカウント新規登録ユースケース。"""

    def __init__(
        self,
        staff_repository: StaffRepository,
        store_repository: StaffStoreReference,
        uniqueness_service: StaffCodeUniquenessService,
        assignment_service: StaffStoreAssignmentService,
        corporate_access: CorporateAccessBoundary,
        account_registration: StaffAccountRegistrationBoundary,
        unit_of_work: UnitOfWork,
        lock: OrganizationLock,
        clock: Clock,
        store_managers: StoreManagerAssignmentRepository,
    ) -> None:
        self._staff_repository = staff_repository
        self._store_repository = store_repository
        self._uniqueness_service = uniqueness_service
        self._assignment_service = assignment_service
        self._corporate_access = corporate_access
        self._account_registration = account_registration
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._clock = clock
        self._store_managers = store_managers

    def _build_qualifications(
        self, command: RegisterStaffCommand
    ) -> StaffQualifications:
        """コマンドの入力値から資格プロファイル一覧を組み立てる。"""
        profiles: list[BaseQualificationProfile] = []
        raw_pharmacist_num = to_optional_text(command.pharmacist_license_number)
        if raw_pharmacist_num:
            license_num = PharmacistLicenseNumber(raw_pharmacist_num)
            insurance_reg = None
            raw_ins_num = to_optional_text(
                command.insurance_pharmacist_registration_number
            )
            if raw_ins_num and command.insurance_pharmacist_registration_date:
                insurance_reg = InsurancePharmacistRegistration(
                    registration_number=InsurancePharmacistRegistrationNumber(
                        raw_ins_num
                    ),
                    registration_date=command.insurance_pharmacist_registration_date,
                )
            profiles.append(
                PharmacistProfile(
                    license_number=license_num, insurance_registration=insurance_reg
                )
            )
        raw_seller_num = to_optional_text(command.registered_seller_number)
        if raw_seller_num:
            profiles.append(
                RegisteredSellerProfile(
                    registration_number=SellerRegistrationNumber(raw_seller_num)
                )
            )
        raw_dietitian_num = to_optional_text(command.dietitian_registration_number)
        if raw_dietitian_num:
            profiles.append(
                DietitianProfile(
                    registration_number=DietitianRegistrationNumber(raw_dietitian_num),
                    is_registered_dietitian=command.is_registered_dietitian,
                )
            )
        return (
            StaffQualifications.from_profiles(*profiles)
            if profiles
            else StaffQualifications.empty()
        )

    async def execute(self, command: RegisterStaffCommand) -> BulkRegisteredStaffResult:
        """スタッフとアカウントを一括登録し、識別子群を返す。"""
        if command.account is None:
            raise DomainValidationError("スタッフ登録にはアカウント情報が必要です。")
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)

        actor = self._corporate_access.actor
        is_admin = bool(
            actor.roles & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        )
        if is_admin:
            await self._corporate_access.require_active(
                corporate_id=corporate_id, permission=Permission.MANAGE_STAFF
            )
        else:
            await self._corporate_access.require_active(
                corporate_id=corporate_id, permission=Permission.MANAGE_STORE_USERS
            )
            if command.account.role not in {"store_operator", "store_viewer"}:
                raise AuthorizationError("管理薬剤師は管理者権限を付与できません。")
            if not isinstance(actor, ResolvedActorContext):
                raise AuthorizationError("有効な管理薬剤師の任命が必要です。")
            managed_store_ids = set(actor.managed_store_ids)
            if not managed_store_ids:
                raise AuthorizationError("有効な管理薬剤師の任命が必要です。")
            if command.initial_home_store_id is None:
                raise AuthorizationError("自管理店舗を主所属として指定してください。")
            home_store = StoreId.parse(command.initial_home_store_id)
            if home_store not in managed_store_ids:
                raise NotFoundError("指定された店舗が見つかりません。")
            if command.account.store_ids:
                for sid in command.account.store_ids:
                    if StoreId.parse(sid) not in managed_store_ids:
                        raise NotFoundError("指定された店舗が見つかりません。")

        await self._lock.acquire("identity")
        await self._lock.acquire(f"corporate:{corporate_id.value}")

        if not is_admin:
            assert isinstance(actor, ResolvedActorContext)
            assert command.initial_home_store_id is not None
            home_store = StoreId.parse(command.initial_home_store_id)
            today = business_date(self._clock)
            appointment = await self._store_managers.find_effective(
                corporate_id, home_store, today
            )
            staff = (
                await self._staff_repository.get(
                    corporate_id=corporate_id, staff_id=actor.staff_id
                )
                if actor.staff_id
                else None
            )
            if (
                appointment is None
                or appointment.staff_id != actor.staff_id
                or appointment.person_id != actor.person_id
                or staff is None
                or not staff.is_active
                or not staff.is_pharmacist
                or staff.current_home_store_id(today) != home_store
            ):
                raise AuthorizationError("現在有効な管理薬剤師の任命と所属が必要です。")
            await self._account_registration.require_active_actor(
                actor=actor, corporate_id=corporate_id, store_id=home_store
            )

        raw_code = to_optional_text(command.code)
        code = StaffCode(raw_code) if raw_code else None
        if code is not None:
            await self._uniqueness_service.ensure_code_is_unique(
                corporate_id=corporate_id, code=code
            )
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
        raw_phone = to_optional_text(command.phone_number)
        phone_number = StaffPhoneNumber(raw_phone) if raw_phone else None
        raw_email = to_optional_text(command.email)
        email = StaffEmailAddress(raw_email) if raw_email else None
        raw_job_title = to_optional_text(command.job_title)
        job_title = JobTitle(raw_job_title) if raw_job_title else None
        qualifications = self._build_qualifications(command)
        staff = Staff(
            id=StaffId.generate(),
            corporate_id=corporate_id,
            names=names,
            qualifications=qualifications,
            job_title=job_title,
            code=code,
            phone_number=phone_number,
            email=email,
            employment_type=(
                EmploymentType(command.employment_type)
                if command.employment_type
                else EmploymentType.REGULAR
            ),
            weekly_contract_hours=(
                WeeklyContractHours(Decimal(str(command.weekly_contract_hours)))
                if command.weekly_contract_hours is not None
                else None
            ),
            affiliations=(),
        )
        if command.initial_home_store_id and command.initial_start_date:
            store_id = StoreId.parse(command.initial_home_store_id)
            store = await load_store_or_raise(
                self._store_repository, corporate_id=corporate_id, store_id=store_id
            )
            staff = self._assignment_service.assign_home_store(
                staff, store, command.initial_start_date
            )
        await self._staff_repository.save(staff)

        if command.account.store_ids is not None:
            account_stores = frozenset(
                StoreId.parse(raw) for raw in command.account.store_ids
            )
        elif command.initial_home_store_id:
            account_stores = frozenset([StoreId.parse(command.initial_home_store_id)])
        else:
            account_stores = frozenset()

        reg_result = await self._account_registration.register_account(
            corporate_id=corporate_id,
            staff_id=staff.id,
            names=names,
            email=command.account.email,
            password=command.account.password,
            role=command.account.role,
            store_ids=account_stores,
        )

        return BulkRegisteredStaffResult(
            staff_id=str(staff.id.value),
            person_id=str(reg_result.person_id.value),
            account_id=str(reg_result.account_id.value),
            membership_id=str(reg_result.membership_id.value),
            email=reg_result.email,
        )
