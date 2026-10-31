"""店舗テストで共有する組み立てヘルパー。

``Store`` はフィールドが多く、各テストで丸ごと組み立てると Arrange が読みづらく
なるため、既定値を持つファクトリをここへ集約する。ドメイン層テストと
アプリケーション層テストの双方から使う。
"""

from __future__ import annotations

from datetime import date
from typing import cast

from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.identifiers import StaffId
from app.domain.store.entities import Store, StoreManagerAssignment
from app.domain.store.identifiers import StoreId, StoreManagerAssignmentId
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    NarcoticsLicenseNumber,
    PharmacyLicenseNumber,
    StoreAddressLine,
    StoreCode,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.value_objects import (
    ContactInfo,
    ManagerAssignmentPeriod,
    NarcoticsRetailerLicense,
    PharmacyLicense,
    StoreAddress,
    StoreLicenses,
    StoreNames,
)

#: 有効な保険薬局指定番号（都道府県コード13・調剤区分4）。
VALID_INSURANCE_NUMBER = "1341234567"


def create_store_names(
    name: str = "サンプル薬局",
    kana: str = "サンプルヤッキョク",
    romaji: str | None = None,
) -> StoreNames:
    return StoreNames(
        name=StoreName(name),
        kana=StoreNameKana(kana),
        romaji=StoreNameRomaji(romaji) if romaji else None,
    )


def create_store_address(
    postal_code: str = "1234567",
    address: str = "東京都千代田区1-2-3",
) -> StoreAddress:
    return StoreAddress(
        postal_code=StorePostalCode(postal_code),
        address=StoreAddressLine(address),
    )


def create_contact_info(
    phone_number: str = "0312345678",
    fax_number: str | None = None,
    email: str | None = None,
) -> ContactInfo:
    return ContactInfo(
        phone_number=StorePhoneNumber(phone_number),
        fax_number=StoreFaxNumber(fax_number) if fax_number else None,
        email=StoreEmailAddress(email) if email else None,
    )


def create_manager_assignment(
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    staff_id: StaffId | None = None,
    person_id: AccountPersonId | None = None,
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
) -> StoreManagerAssignment:
    """店舗に在任する管理薬剤師の任命を組み立てる（永続化はしない）。

    本人を省いたときは新しく採番する。専任義務の競合を確かめるテストは、
    同じ人物であることが要点なので必ず明示的に渡すこと。
    """
    return StoreManagerAssignment(
        id=StoreManagerAssignmentId.generate(),
        corporate_id=corporate_id,
        store_id=store_id,
        staff_id=staff_id if staff_id is not None else StaffId.generate(),
        person_id=person_id if person_id is not None else AccountPersonId.generate(),
        period=ManagerAssignmentPeriod(starts_on=starts_on, ends_on=ends_on),
    )


_DEFAULT_LICENSES: object = object()


def create_store_licenses(
    *,
    pharmacy_license_number: str = "薬-2026-001",
    pharmacy_valid_from: date = date(2020, 1, 1),
    pharmacy_valid_to: date = date(2035, 12, 31),
    narcotics_license_number: str | None = None,
    narcotics_valid_from: date | None = None,
    narcotics_valid_to: date | None = None,
) -> StoreLicenses:
    """店舗の許認可（薬局許可・麻薬免許）を組み立てる。"""
    pharmacy_license = PharmacyLicense(
        number=PharmacyLicenseNumber(pharmacy_license_number),
        valid_from=pharmacy_valid_from,
        valid_to=pharmacy_valid_to,
    )
    narcotics_license = None
    if narcotics_license_number is not None:
        n_valid_from = narcotics_valid_from or date(2026, 10, 29)
        n_valid_to = narcotics_valid_to or date(n_valid_from.year + 2, 12, 31)
        narcotics_license = NarcoticsRetailerLicense(
            number=NarcoticsLicenseNumber(narcotics_license_number),
            valid_from=n_valid_from,
            valid_to=n_valid_to,
        )
    return StoreLicenses(
        pharmacy_license=pharmacy_license,
        narcotics_retailer_license=narcotics_license,
    )


def create_store(
    *,
    corporate_id: CorporateId | None = None,
    name: str = "サンプル薬局",
    kana: str = "サンプルヤッキョク",
    code: str | None = None,
    insurance_pharmacy_number: str | None = None,
    licenses: StoreLicenses | None | object = _DEFAULT_LICENSES,
) -> Store:
    """既定値を持つ店舗を組み立てる（永続化はしない）。"""
    actual_licenses = (
        create_store_licenses()
        if licenses is _DEFAULT_LICENSES
        else cast(StoreLicenses | None, licenses)
    )
    return Store(
        id=StoreId.generate(),
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        code=StoreCode(code) if code else None,
        names=create_store_names(name=name, kana=kana),
        address=create_store_address(),
        contact_info=create_contact_info(),
        insurance_pharmacy_number=InsurancePharmacyNumber(insurance_pharmacy_number)
        if insurance_pharmacy_number
        else None,
        licenses=actual_licenses,
    )
