"""店舗許認可の永続化マッピングとJSON codec・不整合検出テスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.store.entities import Store
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    NarcoticsLicenseNumber,
    PharmacyLicenseNumber,
    StoreAddressLine,
    StoreCode,
    StoreName,
    StoreNameKana,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.value_objects import (
    ContactInfo,
    NarcoticsRetailerLicense,
    PharmacyLicense,
    StoreAddress,
    StoreLicenses,
    StoreNames,
)
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.store.postgres.store import STORE_MAPPING


def _sample_store(
    *,
    with_narcotics: bool = True,
    licenses: StoreLicenses | None = None,
) -> Store:
    if licenses is None:
        pharmacy_lic = PharmacyLicense(
            number=PharmacyLicenseNumber("薬-2026-001"),
            valid_from=date(2026, 10, 29),
            valid_to=date(2032, 10, 28),
        )
        narcotics_lic = (
            NarcoticsRetailerLicense(
                number=NarcoticsLicenseNumber("麻-2026-001"),
                valid_from=date(2026, 10, 29),
                valid_to=date(2028, 12, 31),
            )
            if with_narcotics
            else None
        )
        licenses = StoreLicenses(
            pharmacy_license=pharmacy_lic,
            narcotics_retailer_license=narcotics_lic,
        )

    return Store(
        id=StoreId.generate(),
        corporate_id=CorporateId.generate(),
        names=StoreNames(
            name=StoreName("テスト薬局 中央店"),
            kana=StoreNameKana("テストヤッキョク チュウオウテン"),
        ),
        address=StoreAddress(
            postal_code=StorePostalCode("100-0001"),
            address=StoreAddressLine("東京都千代田区千代田1-1"),
        ),
        contact_info=ContactInfo(
            phone_number=StorePhoneNumber("03-1234-5678"),
        ),
        code=StoreCode("STORE-001"),
        insurance_pharmacy_number=InsurancePharmacyNumber("1340000001"),
        licenses=licenses,
    )


def test_店舗免許は_json_codecで完全往復する() -> None:
    # Arrange: 薬局許可＋麻薬免許を持つ店舗
    store_both = _sample_store(with_narcotics=True)
    store_pharmacy_only = _sample_store(with_narcotics=False)
    store_none = _sample_store(licenses=None)

    # Act & Assert
    for store in [store_both, store_pharmacy_only, store_none]:
        encoded = encode_aggregate(store)
        restored = decode_aggregate(encoded, Store)

        assert restored.id == store.id
        assert restored.corporate_id == store.corporate_id
        assert restored.names == store.names
        assert restored.licenses == store.licenses


def test_店舗免許の検索列がpayloadと食い違えば復元を拒否する() -> None:
    # Arrange: 薬局許可＋麻薬免許の完全な行データを生成
    store = _sample_store(with_narcotics=True)
    row = STORE_MAPPING.row_values(store)

    # 正常な行は復元できる
    decoded = STORE_MAPPING.decode(row)
    assert decoded.id == store.id

    # 6つの検索列それぞれを改ざんした場合に拒否されることを検証
    license_columns = [
        ("pharmacy_license_number", "改ざん番号"),
        ("pharmacy_license_valid_from", date(2020, 1, 1)),
        ("pharmacy_license_valid_to", date(2040, 1, 1)),
        ("narcotics_license_number", "改ざん麻薬番号"),
        ("narcotics_license_valid_from", date(2020, 1, 1)),
        ("narcotics_license_valid_to", date(2040, 12, 31)),
    ]

    for col_name, corrupted_val in license_columns:
        corrupted_row = dict(row)
        corrupted_row[col_name] = corrupted_val

        with pytest.raises(PersistenceMappingError) as exc_info:
            STORE_MAPPING.decode(corrupted_row)
        assert col_name in str(exc_info.value)
