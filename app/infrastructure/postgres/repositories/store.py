"""店舗の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    StoreCode,
    StoreId,
    StoreName,
)
from app.domain.store.repository import StoreCatalogRepository, StoreRepository
from app.domain.store.store import Store
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import stores


def row_values(store: Store) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": store.id.value,
        "corporate_id": store.corporate_id.value,
        "name": store.names.name.value,
        "code": None if store.code is None else store.code.value,
        "insurance_pharmacy_number": (
            None
            if store.insurance_pharmacy_number is None
            else store.insurance_pharmacy_number.value
        ),
        "payload": encode_aggregate(store),
    }


class PostgresStoreRepository(
    PostgresRepositoryBase, StoreRepository, StoreCatalogRepository
):
    """店舗集約を PostgreSQL へ保存・検索する。"""

    async def get(self, store_id: StoreId) -> Store | None:
        """IDで店舗を検索する。"""
        result = await self.session.execute(
            select(stores).where(stores.c.id == store_id.value)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=stores.name,
            )
        )

    async def save(self, store: Store) -> None:
        """店舗を保存し、店舗名・店舗コード・保険薬局指定番号の重複を拒否する。"""
        try:
            await self.upsert(
                stores, aggregate_id=store.id.value, values=row_values(store)
            )
        except IntegrityError as error:
            violated = constraint_name(error)
            if violated == "uq_stores_corporate_name":
                raise StoreNameAlreadyExistsError(
                    f"同一法人内に店舗名 '{store.names.name.value}' は既に登録されています。"
                ) from error
            if violated == "uq_stores_corporate_code":
                raise StoreCodeAlreadyExistsError(
                    f"同一法人内に店舗コード '{store.code}' は既に登録されています。"
                ) from error
            if violated == "uq_stores_insurance_pharmacy_number":
                raise InsurancePharmacyNumberAlreadyExistsError(
                    f"保険薬局指定番号 '{store.insurance_pharmacy_number}' "
                    "は既に別の店舗で登録されています。"
                ) from error
            raise

    async def exists_by_name(
        self,
        *,
        corporate_id: CorporateId,
        name: StoreName,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """同一法人内で店舗名が使われているかを検索する。"""
        statement = select(stores.c.id).where(
            stores.c.corporate_id == corporate_id.value,
            stores.c.name == name.value,
        )
        return await self._exists(statement, excluding_id)

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StoreCode,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """同一法人内で店舗コードが使われているかを検索する。"""
        statement = select(stores.c.id).where(
            stores.c.corporate_id == corporate_id.value,
            stores.c.code == code.value,
        )
        return await self._exists(statement, excluding_id)

    async def exists_by_insurance_pharmacy_number(
        self,
        *,
        number: InsurancePharmacyNumber,
        excluding_id: StoreId | None = None,
    ) -> bool:
        """保険薬局指定番号が別の店舗で使われているかを検索する。

        指定番号は法人をまたいで一意なので、法人では絞らない。
        """
        statement = select(stores.c.id).where(
            stores.c.insurance_pharmacy_number == number.value
        )
        return await self._exists(statement, excluding_id)

    async def list_by_corporate_id(self, corporate_id: CorporateId) -> list[Store]:
        """法人の店舗を名前順で返す。"""
        result = await self.session.execute(
            select(stores)
            .where(stores.c.corporate_id == corporate_id.value)
            .order_by(stores.c.name, stores.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=stores.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def list_all(self) -> list[Store]:
        """ベンダー用に全店舗を法人・名前順で返す。"""
        result = await self.session.execute(
            select(stores).order_by(stores.c.corporate_id, stores.c.name, stores.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=stores.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def _exists(
        self, statement: Select[Any], excluding_id: StoreId | None
    ) -> bool:
        """自分自身を除いて1件でも該当するかを返す。"""
        if excluding_id is not None:
            statement = statement.where(stores.c.id != excluding_id.value)
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None


def _decode_row(row: Mapping[str, object]) -> Store:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "店舗の payload が JSON オブジェクトではありません。"
        )
    store = decode_aggregate(payload, Store)
    code = None if store.code is None else store.code.value
    number = (
        None
        if store.insurance_pharmacy_number is None
        else store.insurance_pharmacy_number.value
    )
    if (
        store.id.value != row.get("id")
        or store.corporate_id.value != row.get("corporate_id")
        or store.names.name.value != row.get("name")
        or code != row.get("code")
        or number != row.get("insurance_pharmacy_number")
    ):
        raise PersistenceMappingError("店舗の検索列と payload が一致しません。")
    return store
