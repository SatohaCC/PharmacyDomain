"""法人の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.corporate.primitives import CorporateId, CorporateName
from app.domain.corporate.repository import (
    CorporateCatalogRepository,
    CorporateRepository,
)
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import corporates


def row_values(corporate: Corporate) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": corporate.id.value,
        "name": corporate.name.value,
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
        "payload": encode_aggregate(corporate),
    }


class PostgresCorporateRepository(
    PostgresRepositoryBase, CorporateRepository, CorporateCatalogRepository
):
    """法人集約を PostgreSQL へ保存・検索する。"""

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        """IDで法人を検索する。"""
        result = await self.session.execute(
            select(corporates).where(corporates.c.id == corporate_id.value)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=corporates.name,
            )
        )

    async def save(self, corporate: Corporate) -> None:
        """法人を新規登録または更新し、法人名の重複をDBで拒否する。"""
        try:
            await self.upsert(
                corporates,
                aggregate_id=corporate.id.value,
                values=row_values(corporate),
            )
        except IntegrityError as error:
            if constraint_name(error) == "uq_corporates_name":
                raise CorporateNameAlreadyExistsError() from error
            raise

    async def exists_by_name(
        self,
        name: CorporateName,
        *,
        excluding_id: CorporateId | None = None,
    ) -> bool:
        """法人名が既に使われているかを検索する。"""
        statement = select(corporates.c.id).where(corporates.c.name == name.value)
        if excluding_id is not None:
            statement = statement.where(corporates.c.id != excluding_id.value)
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_all(self) -> list[Corporate]:
        """ベンダー用に全法人を名前順で返す。"""
        result = await self.session.execute(
            select(corporates).order_by(corporates.c.name, corporates.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=corporates.name,
                )
            )
            for row in result.mappings().all()
        ]


def _decode_row(row: Mapping[str, object]) -> Corporate:
    """DB行のpayloadと検索列の整合性を確認して法人を復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "法人の payload が JSON オブジェクトではありません。"
        )
    corporate = decode_aggregate(payload, Corporate)
    if (
        corporate.id.value != row.get("id")
        or corporate.name.value != row.get("name")
        or corporate.representative_name.full_name != row.get("representative_name")
        or corporate.status.value != row.get("status")
    ):
        raise PersistenceMappingError("法人の検索列と payload が一致しません。")
    return corporate
