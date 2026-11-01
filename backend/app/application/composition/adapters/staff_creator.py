"""初期管理者へのスタッフ紐付けアダプタ。"""

from __future__ import annotations

from datetime import date

from app.application.common.input_normalization import to_optional_text
from app.application.identity.interfaces.staff_creator import StaffCreationBoundary
from app.application.staff.interfaces.references import StaffStoreReference
from app.application.store.errors import StoreNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import (
    DietitianRegistrationNumber,
    InsurancePharmacistRegistrationNumber,
    JobTitle,
    PharmacistLicenseNumber,
    SellerRegistrationNumber,
    StaffCode,
    StaffEmailAddress,
    StaffPhoneNumber,
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
    StoreSource,
)
from app.domain.store.identifiers import StoreId


class StaffCreationAdapter(StaffCreationBoundary):
    """Staffドメインの集約生成・保存を実装する。"""

    def __init__(
        self,
        staff_repository: StaffRepository,
        store_repository: StaffStoreReference,
        uniqueness_service: StaffCodeUniquenessService,
        assignment_service: StaffStoreAssignmentService,
    ) -> None:
        self._staff_repository = staff_repository
        self._store_repository = store_repository
        self._uniqueness_service = uniqueness_service
        self._assignment_service = assignment_service

    def _build_qualifications(
        self,
        *,
        pharmacist_license_number: str | None,
        insurance_pharmacist_registration_number: str | None,
        insurance_pharmacist_registration_date: date | None,
        registered_seller_number: str | None,
        dietitian_registration_number: str | None,
        is_registered_dietitian: bool,
    ) -> StaffQualifications:
        profiles: list[BaseQualificationProfile] = []
        raw_pharmacist_num = to_optional_text(pharmacist_license_number)
        if raw_pharmacist_num:
            license_num = PharmacistLicenseNumber(raw_pharmacist_num)
            insurance_reg = None
            raw_ins_num = to_optional_text(insurance_pharmacist_registration_number)
            if raw_ins_num and insurance_pharmacist_registration_date:
                insurance_reg = InsurancePharmacistRegistration(
                    registration_number=InsurancePharmacistRegistrationNumber(
                        raw_ins_num
                    ),
                    registration_date=insurance_pharmacist_registration_date,
                )
            profiles.append(
                PharmacistProfile(
                    license_number=license_num, insurance_registration=insurance_reg
                )
            )
        raw_seller_num = to_optional_text(registered_seller_number)
        if raw_seller_num:
            profiles.append(
                RegisteredSellerProfile(
                    registration_number=SellerRegistrationNumber(raw_seller_num)
                )
            )
        raw_dietitian_num = to_optional_text(dietitian_registration_number)
        if raw_dietitian_num:
            profiles.append(
                DietitianProfile(
                    registration_number=DietitianRegistrationNumber(raw_dietitian_num),
                    is_registered_dietitian=is_registered_dietitian,
                )
            )
        return (
            StaffQualifications.from_profiles(*profiles)
            if profiles
            else StaffQualifications.empty()
        )

    async def create_staff(
        self,
        *,
        corporate_id: CorporateId,
        names: PersonNames,
        code: str | None,
        job_title: str | None,
        phone_number: str | None,
        email: str | None,
        initial_home_store_id: str | None,
        initial_start_date: date | None,
        pharmacist_license_number: str | None,
        insurance_pharmacist_registration_number: str | None,
        insurance_pharmacist_registration_date: date | None,
        registered_seller_number: str | None,
        dietitian_registration_number: str | None,
        is_registered_dietitian: bool,
    ) -> StaffId:
        raw_code = to_optional_text(code)
        staff_code = StaffCode(raw_code) if raw_code else None
        if staff_code is not None:
            await self._uniqueness_service.ensure_code_is_unique(
                corporate_id=corporate_id, code=staff_code
            )
        raw_phone = to_optional_text(phone_number)
        phone = StaffPhoneNumber(raw_phone) if raw_phone else None
        raw_email = to_optional_text(email)
        mail = StaffEmailAddress(raw_email) if raw_email else None
        raw_job = to_optional_text(job_title)
        job = JobTitle(raw_job) if raw_job else None

        qualifications = self._build_qualifications(
            pharmacist_license_number=pharmacist_license_number,
            insurance_pharmacist_registration_number=insurance_pharmacist_registration_number,
            insurance_pharmacist_registration_date=insurance_pharmacist_registration_date,
            registered_seller_number=registered_seller_number,
            dietitian_registration_number=dietitian_registration_number,
            is_registered_dietitian=is_registered_dietitian,
        )

        staff = Staff(
            id=StaffId.generate(),
            corporate_id=corporate_id,
            names=names,
            qualifications=qualifications,
            job_title=job,
            code=staff_code,
            phone_number=phone,
            email=mail,
            affiliations=(),
        )
        if initial_home_store_id and initial_start_date:
            store_id = StoreId.parse(initial_home_store_id)
            store = await self._load_store_or_raise(
                corporate_id=corporate_id, store_id=store_id
            )
            staff = self._assignment_service.assign_home_store(
                staff, store, initial_start_date
            )
        await self._staff_repository.save(staff)
        return staff.id

    async def _load_store_or_raise(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> StoreSource:
        store = await self._store_repository.get(
            corporate_id=corporate_id, store_id=store_id
        )
        if store is None:
            raise StoreNotFoundError(
                f"指定された店舗（ID: {store_id.value}）が見つかりません。"
            )
        return store
