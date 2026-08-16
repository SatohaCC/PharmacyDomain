"""店舗テストで共有する組み立てヘルパー。

``Store`` はフィールドが多く、各テストで丸ごと組み立てると Arrange が読みづらく
なるため、既定値を持つファクトリをここへ集約する。ドメイン層テストと
アプリケーション層テストの双方から使う。
"""

from __future__ import annotations

from app.domain.corporate import CorporateId
from app.domain.store import (
    ContactInfo,
    InsurancePharmacyNumber,
    Store,
    StoreAddress,
    StoreAddressLine,
    StoreCode,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
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
    return ContactInfo.create(
        phone_number=StorePhoneNumber(phone_number),
        fax_number=StoreFaxNumber(fax_number) if fax_number else None,
        email=StoreEmailAddress(email) if email else None,
    )


def create_store(
    *,
    corporate_id: CorporateId | None = None,
    name: str = "サンプル薬局",
    kana: str = "サンプルヤッキョク",
    code: str | None = None,
    insurance_pharmacy_number: str | None = None,
) -> Store:
    """既定値を持つ店舗を組み立てる（永続化はしない）。"""
    return Store.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        names=create_store_names(name=name, kana=kana),
        address=create_store_address(),
        contact_info=create_contact_info(),
        code=StoreCode(code) if code else None,
        insurance_pharmacy_number=(
            InsurancePharmacyNumber(insurance_pharmacy_number)
            if insurance_pharmacy_number
            else None
        ),
    )
