"""店舗許認可のトランザクション・整合性・実DB永続化テスト（TC-005, TC-006）。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateName,
    CorporateStatus,
)
from app.domain.corporate.value_objects import CorporateRepresentativeName
from app.domain.shared.person_name import PersonNamePart
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
from app.infrastructure.corporate.postgres.corporate import PostgresCorporateRepository
from app.infrastructure.postgres.codec import PersistenceMappingError
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.store.postgres.store import PostgresStoreRepository


def _make_store(
    corporate_id: CorporateId,
    store_id: StoreId,
    licenses: StoreLicenses | None,
) -> Store:
    return Store(
        id=store_id,
        corporate_id=corporate_id,
        names=StoreNames(
            name=StoreName("テスト薬局 本店"),
            kana=StoreNameKana("テストヤッキョク ホンテン"),
        ),
        address=StoreAddress(
            postal_code=StorePostalCode("100-0001"),
            address=StoreAddressLine("東京都千代田区千代田1-1"),
        ),
        contact_info=ContactInfo(
            phone_number=StorePhoneNumber("03-1234-5678"),
        ),
        code=StoreCode("STORE-HON"),
        insurance_pharmacy_number=InsurancePharmacyNumber("1340000001"),
        licenses=licenses,
    )


@pytest.mark.integration
async def test_TC005_店舗免許を別UoWから復元し麻薬免許だけを置換する(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()

    # 1. 法人と店舗（薬局開設許可＋麻薬免許あり）を保存
    pharmacy_lic = PharmacyLicense(
        number=PharmacyLicenseNumber("薬-2026-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2032, 10, 28),
    )
    narcotics_lic = NarcoticsRetailerLicense(
        number=NarcoticsLicenseNumber("麻-2026-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2028, 12, 31),
    )
    initial_licenses = StoreLicenses(
        pharmacy_license=pharmacy_lic,
        narcotics_retailer_license=narcotics_lic,
    )
    store = _make_store(corporate_id, store_id, initial_licenses)

    async with PostgresUnitOfWork(session_factory) as uow:
        corp_repo = PostgresCorporateRepository(uow)
        await corp_repo.save(
            Corporate(
                id=corporate_id,
                name=CorporateName("テスト薬局法人"),
                representative_name=CorporateRepresentativeName(
                    last_name=PersonNamePart("代表"),
                    first_name=PersonNamePart("太郎"),
                ),
                status=CorporateStatus.ACTIVE,
            )
        )
        store_repo = PostgresStoreRepository(uow)
        await store_repo.save(store)
        await uow.commit()

    # 2. 別のUoWで取得し、検索列・内容が保持されていることを確認
    async with PostgresUnitOfWork(session_factory) as uow:
        store_repo = PostgresStoreRepository(uow)
        fetched = await store_repo.get(store_id)
        assert fetched is not None
        assert fetched.licenses is not None
        assert fetched.licenses.pharmacy_license.number.value == "薬-2026-001"
        assert fetched.licenses.pharmacy_license.valid_from == date(2026, 10, 29)
        assert fetched.licenses.pharmacy_license.valid_to == date(2032, 10, 28)
        assert fetched.licenses.narcotics_retailer_license is not None
        assert fetched.licenses.narcotics_retailer_license.number.value == "麻-2026-001"
        assert fetched.licenses.narcotics_retailer_license.valid_to == date(
            2028, 12, 31
        )

        # 3. 麻薬免許を None に置換して保存
        updated_licenses = StoreLicenses(
            pharmacy_license=pharmacy_lic,
            narcotics_retailer_license=None,
        )
        updated_store = fetched.update_licenses(updated_licenses)
        await store_repo.save(updated_store)
        await uow.commit()

    # 4. 別UoWで再取得し、麻薬免許が削除され薬局許可が残っていることを確認
    async with PostgresUnitOfWork(session_factory) as uow:
        store_repo = PostgresStoreRepository(uow)
        refetched = await store_repo.get(store_id)
        assert refetched is not None
        assert refetched.licenses is not None
        assert refetched.licenses.pharmacy_license.number.value == "薬-2026-001"
        assert refetched.licenses.narcotics_retailer_license is None


@pytest.mark.integration
async def test_TC006_店舗免許の検索列ごとのpayload不一致を復元時に拒否する(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()

    pharmacy_lic = PharmacyLicense(
        number=PharmacyLicenseNumber("薬-2026-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2032, 10, 28),
    )
    narcotics_lic = NarcoticsRetailerLicense(
        number=NarcoticsLicenseNumber("麻-2026-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2028, 12, 31),
    )
    licenses = StoreLicenses(
        pharmacy_license=pharmacy_lic,
        narcotics_retailer_license=narcotics_lic,
    )
    store = _make_store(corporate_id, store_id, licenses)

    async with PostgresUnitOfWork(session_factory) as uow:
        corp_repo = PostgresCorporateRepository(uow)
        await corp_repo.save(
            Corporate(
                id=corporate_id,
                name=CorporateName("テスト薬局法人"),
                representative_name=CorporateRepresentativeName(
                    last_name=PersonNamePart("代表"),
                    first_name=PersonNamePart("太郎"),
                ),
                status=CorporateStatus.ACTIVE,
            )
        )
        store_repo = PostgresStoreRepository(uow)
        await store_repo.save(store)
        await uow.commit()

    # 各列を直接SQLで改ざんし、Repository経由でgetした時にPersistenceMappingErrorとなることを確認
    license_columns = [
        ("pharmacy_license_number", "'改ざん番号'"),
        ("pharmacy_license_valid_from", "'2020-01-01'"),
        ("pharmacy_license_valid_to", "'2040-01-01'"),
        ("narcotics_license_number", "'改ざん麻薬番号'"),
        ("narcotics_license_valid_from", "'2020-01-01'"),
        ("narcotics_license_valid_to", "'2040-12-31'"),
    ]

    for col_name, sql_val in license_columns:
        async with PostgresUnitOfWork(session_factory) as uow:
            # 直接SQLで改ざん
            await uow.session.execute(
                text(f"UPDATE stores SET {col_name} = {sql_val} WHERE id = :id"),
                {"id": store_id.value},
            )
            await uow.commit()

        async with PostgresUnitOfWork(session_factory) as uow:
            store_repo = PostgresStoreRepository(uow)
            with pytest.raises(PersistenceMappingError) as exc_info:
                await store_repo.get(store_id)
            assert col_name in str(exc_info.value)
