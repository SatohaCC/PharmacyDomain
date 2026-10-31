"""Applicationのupdate_licensesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.services.support import load_store_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import NarcoticsLicenseNumber, PharmacyLicenseNumber
from app.domain.store.repositories import StoreRepository
from app.domain.store.value_objects import (
    NarcoticsRetailerLicense,
    PharmacyLicense,
    StoreLicenses,
)


@dataclass(frozen=True, kw_only=True)
class PharmacyLicenseInput:
    """薬局開設許可の入力データ。"""

    number: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class NarcoticsRetailerLicenseInput:
    """麻薬小売業者免許の入力データ。"""

    number: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class UpdateStoreLicensesCommand:
    """店舗許認可更新に必要な入力データ（DTO）。"""

    corporate_id: str
    store_id: str
    pharmacy_license: PharmacyLicenseInput
    narcotics_retailer_license: NarcoticsRetailerLicenseInput | None = None


class UpdateStoreLicensesUseCase:
    """店舗許認可更新ユースケース。"""

    def __init__(
        self, repository: StoreRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdateStoreLicensesCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        pharmacy_license = PharmacyLicense(
            number=PharmacyLicenseNumber(command.pharmacy_license.number),
            valid_from=command.pharmacy_license.valid_from,
            valid_to=command.pharmacy_license.valid_to,
        )
        narcotics_license = None
        if command.narcotics_retailer_license is not None:
            narcotics_license = NarcoticsRetailerLicense(
                number=NarcoticsLicenseNumber(
                    command.narcotics_retailer_license.number
                ),
                valid_from=command.narcotics_retailer_license.valid_from,
                valid_to=command.narcotics_retailer_license.valid_to,
            )

        licenses = StoreLicenses(
            pharmacy_license=pharmacy_license,
            narcotics_retailer_license=narcotics_license,
        )
        updated = store.update_licenses(licenses)
        await self._repository.save(updated)
