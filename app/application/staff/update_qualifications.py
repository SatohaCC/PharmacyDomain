"""スタッフ資格情報更新ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.staff.support import load_staff_or_raise, to_optional_text
from app.base.domain.primitives.primitives import BaseNormalizedString
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import (
    BaseQualificationProfile,
    DietitianProfile,
    DietitianRegistrationNumber,
    InsurancePharmacistRegistration,
    PharmacistLicenseNumber,
    PharmacistProfile,
    RegisteredSellerProfile,
    SellerRegistrationNumber,
    StaffId,
    StaffQualifications,
    StaffRepository,
)


@dataclass(frozen=True, kw_only=True)
class UpdateStaffQualificationsCommand:
    """資格情報更新の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    pharmacist_license_number: str | None = None
    insurance_pharmacist_registration_number: str | None = None
    insurance_pharmacist_registration_date: date | None = None
    registered_seller_number: str | None = None
    dietitian_registration_number: str | None = None
    is_registered_dietitian: bool = True


class UpdateStaffQualificationsUseCase:
    """スタッフ資格情報更新ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    def _build_qualifications(
        self, command: UpdateStaffQualificationsCommand
    ) -> StaffQualifications:
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
                    registration_number=BaseNormalizedString(raw_ins_num),
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

    async def execute(self, command: UpdateStaffQualificationsCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STAFF,
        )
        staff_id = StaffId.parse(command.staff_id)

        staff = await load_staff_or_raise(
            self._repository,
            corporate_id=corporate_id,
            staff_id=staff_id,
        )

        qualifications = self._build_qualifications(command)
        updated_staff = staff.update_qualifications(qualifications)

        await self._repository.save(updated_staff)
