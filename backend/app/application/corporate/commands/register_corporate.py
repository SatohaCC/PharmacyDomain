"""Applicationのregister_corporateを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.corporate.commands.models import RegisterCorporateCommand
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateAddressLine,
    CorporateEmailAddress,
    CorporateName,
    CorporateNumber,
    CorporatePhoneNumber,
    CorporatePostalCode,
    CorporateType,
    InvoiceRegistrationNumber,
)
from app.domain.corporate.repositories import CorporateRepository
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.corporate.value_objects import (
    CorporateAddress,
    CorporateContactInfo,
    CorporateRepresentativeName,
)
from app.domain.shared.person_name import PersonNamePart


class RegisterCorporateUseCase:
    """法人を新規登録するアプリケーションサービス"""

    def __init__(
        self,
        repository: CorporateRepository,
        uniqueness_service: CorporateNameUniquenessService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterCorporateCommand) -> CorporateId:
        AuthorizationService(self._corporate_access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        name = CorporateName(command.name)
        rep_name = CorporateRepresentativeName(
            last_name=PersonNamePart(command.representative_last_name),
            first_name=PersonNamePart(command.representative_first_name),
        )
        await self._uniqueness_service.ensure_name_is_unique(name=name)

        address = (
            CorporateAddress(
                postal_code=CorporatePostalCode(command.postal_code),
                address_line=CorporateAddressLine(command.address_line),
            )
            if command.postal_code and command.address_line
            else None
        )
        contact_info = (
            CorporateContactInfo(
                phone_number=CorporatePhoneNumber(command.phone_number),
                email=(CorporateEmailAddress(command.email) if command.email else None),
            )
            if command.phone_number
            else None
        )

        corporate = Corporate(
            id=CorporateId.generate(),
            name=name,
            representative_name=rep_name,
            corporate_type=(
                CorporateType(command.corporate_type)
                if command.corporate_type
                else CorporateType.STOCK_COMPANY
            ),
            corporate_number=(
                CorporateNumber(command.corporate_number)
                if command.corporate_number
                else None
            ),
            invoice_number=(
                InvoiceRegistrationNumber(command.invoice_number)
                if command.invoice_number
                else None
            ),
            address=address,
            contact_info=contact_info,
        )
        await self._repository.save(corporate)
        return corporate.id
