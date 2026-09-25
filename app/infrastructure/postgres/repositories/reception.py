"""受付RepositoryのPostgreSQLアダプタ。"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.reception import Reception
from app.domain.reception.repository import ReceptionRepository
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.codec import PersistenceMappingError
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import receptions


def _reception_identity(values: Mapping[str, object]) -> UUID:
    """法人・店舗・受付IDの組をUnitOfWork用の安定したUUIDへ変換する。"""
    reception_id = values.get("id")
    corporate_id = values.get("corporate_id")
    store_id = values.get("store_id")
    if not all(
        isinstance(value, UUID) for value in (reception_id, corporate_id, store_id)
    ):
        raise PersistenceMappingError("受付の複合識別子がUUIDではありません。")
    return uuid5(
        NAMESPACE_URL,
        f"pharmacy-domain:reception:{corporate_id}:{store_id}:{reception_id}",
    )


def _reception_columns(reception: Reception) -> dict[str, object]:
    """受付の複合識別子を検索列へ展開する。"""
    return {
        "id": reception.id.value,
        "corporate_id": reception.corporate_id.value,
        "store_id": reception.store_id.value,
    }


RECEPTION_MAPPING = AggregateMapping(
    table=receptions,
    aggregate_type=Reception,
    label="受付",
    search_columns=_reception_columns,
    unit_of_work_identity=_reception_identity,
    conflict_columns=("corporate_id", "store_id", "id"),
)


class PostgresReceptionRepository(PostgresRepositoryBase, ReceptionRepository):
    """受付指紋と訂正履歴をPostgreSQLへ保存するRepository。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Reception | None:
        """法人・店舗・呼出元受付IDが一致する受付を検索する。"""
        return await self.find_one(
            RECEPTION_MAPPING,
            select(receptions).where(
                receptions.c.id == reception_id.value,
                receptions.c.corporate_id == corporate_id.value,
                receptions.c.store_id == store_id.value,
            ),
        )

    async def save(self, reception: Reception) -> None:
        """受付の受信基準を保存する。"""
        await self.save_aggregate(RECEPTION_MAPPING, reception)
