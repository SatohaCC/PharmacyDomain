"""Applicationのupdate_corporate_detailsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateAddressLine,
    CorporateEmailAddress,
    CorporateNumber,
    CorporatePhoneNumber,
    CorporatePostalCode,
    CorporateType,
    InvoiceRegistrationNumber,
)
from app.domain.corporate.repositories import CorporateRepository
from app.domain.corporate.value_objects import CorporateAddress, CorporateContactInfo
from app.domain.foundation.exceptions import DomainValidationError


@dataclass(frozen=True, kw_only=True)
class UpdateCorporateDetailsCommand:
    """法人詳細情報更新コマンド。"""

    corporate_id: str
    corporate_type: str | None = None
    corporate_number: str | None = None
    invoice_number: str | None = None
    postal_code: str | None = None
    address_line: str | None = None
    phone_number: str | None = None
    email: str | None = None


class UpdateCorporateDetailsUseCase:
    """法人詳細情報更新ユースケース。"""

    def __init__(
        self,
        repository: CorporateRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdateCorporateDetailsCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        corporate = await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_CORPORATE
        )

        if command.corporate_type is not None:
            try:
                corp_type = CorporateType(command.corporate_type)
            except ValueError as err:
                raise DomainValidationError(
                    f"不正な法人区分です: '{command.corporate_type}'"
                ) from err
            corporate = corporate.change_corporate_type(corp_type)

        if command.corporate_number is not None:
            num = (
                CorporateNumber(command.corporate_number)
                if command.corporate_number.strip()
                else None
            )
            corporate = corporate.update_corporate_number(num)

        if command.invoice_number is not None:
            inv = (
                InvoiceRegistrationNumber(command.invoice_number)
                if command.invoice_number.strip()
                else None
            )
            corporate = corporate.update_invoice_number(inv)

        # 住所更新
        if command.postal_code is not None or command.address_line is not None:
            postal = (
                command.postal_code.strip()
                if command.postal_code is not None
                else (corporate.address.postal_code.value if corporate.address else "")
            )
            line = (
                command.address_line.strip()
                if command.address_line is not None
                else (corporate.address.address_line.value if corporate.address else "")
            )
            if (bool(postal) != bool(line)) and (postal or line):
                raise DomainValidationError(
                    "所在地を指定する場合は郵便番号と住所行の両方を入力してください。"
                )
            address = (
                CorporateAddress(
                    postal_code=CorporatePostalCode(postal),
                    address_line=CorporateAddressLine(line),
                )
                if postal and line
                else None
            )
            corporate = corporate.change_address(address)

        # 連絡先更新
        if command.phone_number is not None or command.email is not None:
            phone = (
                command.phone_number.strip()
                if command.phone_number is not None
                else (
                    corporate.contact_info.phone_number.value
                    if corporate.contact_info
                    else ""
                )
            )
            mail = (
                command.email.strip()
                if command.email is not None
                else (
                    corporate.contact_info.email.value
                    if corporate.contact_info and corporate.contact_info.email
                    else ""
                )
            )
            if mail and not phone:
                raise DomainValidationError(
                    "連絡先メールアドレスを指定する場合は代表電話番号も入力してください。"
                )
            contact = (
                CorporateContactInfo(
                    phone_number=CorporatePhoneNumber(phone),
                    email=CorporateEmailAddress(mail) if mail else None,
                )
                if phone
                else None
            )
            corporate = corporate.change_contact_info(contact)

        corporate.validate()
        await self._repository.save(corporate)
