"""スタッフ新規登録ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_store_or_raise, to_optional_text
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import (
    BaseQualificationProfile,
    DietitianProfile,
    DietitianRegistrationNumber,
    InsurancePharmacistRegistration,
    InsurancePharmacistRegistrationNumber,
    JobTitle,
    PharmacistLicenseNumber,
    PharmacistProfile,
    RegisteredSellerProfile,
    SellerRegistrationNumber,
    Staff,
    StaffCode,
    StaffCodeUniquenessService,
    StaffEmailAddress,
    StaffPhoneNumber,
    StaffQualifications,
    StaffRepository,
    StaffStoreAssignmentService,
)
from app.domain.store import StoreId, StoreRepository


@dataclass(frozen=True, kw_only=True)
class RegisterStaffCommand:
    """スタッフ新規登録に必要な入力データ（DTO）。"""

    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    job_title: str | None = None
    code: str | None = None
    phone_number: str | None = None
    email: str | None = None
    initial_home_store_id: str | None = None
    initial_start_date: date | None = None
    # --- 資格情報（オプショナル） ---
    pharmacist_license_number: str | None = None
    insurance_pharmacist_registration_number: str | None = None
    insurance_pharmacist_registration_date: date | None = None
    registered_seller_number: str | None = None
    dietitian_registration_number: str | None = None
    is_registered_dietitian: bool = True


class RegisterStaffUseCase:
    """スタッフ新規登録ユースケース。"""

    def __init__(
        self,
        staff_repository: StaffRepository,
        store_repository: StoreRepository,
        uniqueness_service: StaffCodeUniquenessService,
        assignment_service: StaffStoreAssignmentService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._staff_repository = staff_repository
        self._store_repository = store_repository
        self._uniqueness_service = uniqueness_service
        self._assignment_service = assignment_service
        self._corporate_access = corporate_access

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
                    license_number=license_num,
                    insurance_registration=insurance_reg,
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

    async def execute(self, command: RegisterStaffCommand) -> Staff:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STAFF,
        )

        raw_code = to_optional_text(command.code)
        code = StaffCode(raw_code) if raw_code else None

        if code is not None:
            await self._uniqueness_service.ensure_code_is_unique(
                corporate_id=corporate_id,
                code=code,
            )

        names = PersonNames.create(
            last_name=command.last_name,
            first_name=command.first_name,
            last_name_kana=command.last_name_kana,
            first_name_kana=command.first_name_kana,
        )

        raw_phone = to_optional_text(command.phone_number)
        phone_number = StaffPhoneNumber(raw_phone) if raw_phone else None

        raw_email = to_optional_text(command.email)
        email = StaffEmailAddress(raw_email) if raw_email else None

        raw_job_title = to_optional_text(command.job_title)
        job_title = JobTitle(raw_job_title) if raw_job_title else None

        qualifications = self._build_qualifications(command)

        staff = Staff.create(
            corporate_id=corporate_id,
            names=names,
            qualifications=qualifications,
            job_title=job_title,
            code=code,
            phone_number=phone_number,
            email=email,
        )

        if command.initial_home_store_id and command.initial_start_date:
            store_id = StoreId.parse(command.initial_home_store_id)
            store = await load_store_or_raise(
                self._store_repository,
                corporate_id=corporate_id,
                store_id=store_id,
            )
            staff = self._assignment_service.assign_home_store(
                staff,
                store,
                command.initial_start_date,
            )

        await self._staff_repository.save(staff)
        return staff
