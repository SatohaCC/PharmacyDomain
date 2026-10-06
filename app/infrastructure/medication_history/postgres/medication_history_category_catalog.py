"""法人別薬歴記載区分カタログの PostgreSQL Repository。

法人ごとに1件だけ存在する区分カタログなので、法人IDで引く。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.repository import (
    MedicationHistoryCategoryCatalogRepository,
)
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import medication_history_category_catalogs


def _category_catalog_columns(
    catalog: MedicationHistoryCategoryCatalog,
) -> dict[str, object]:
    """検索・一意性制約に使う列をカタログから導く。"""
    return {
        "id": catalog.id.value,
        "corporate_id": catalog.corporate_id.value,
    }


MEDICATION_HISTORY_CATEGORY_CATALOG_MAPPING = AggregateMapping(
    table=medication_history_category_catalogs,
    aggregate_type=MedicationHistoryCategoryCatalog,
    label="薬歴記載区分カタログ",
    search_columns=_category_catalog_columns,
)


class PostgresMedicationHistoryCategoryCatalogRepository(
    PostgresRepositoryBase, MedicationHistoryCategoryCatalogRepository
):
    """法人別薬歴記載区分カタログを PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
    ) -> MedicationHistoryCategoryCatalog | None:
        """法人の区分カタログを取得する。未登録なら ``None``。"""
        return await self.find_one(
            MEDICATION_HISTORY_CATEGORY_CATALOG_MAPPING,
            select(medication_history_category_catalogs).where(
                medication_history_category_catalogs.c.corporate_id
                == corporate_id.value,
            ),
        )

    async def save(self, catalog: MedicationHistoryCategoryCatalog) -> None:
        """法人ごとに1件であることを原子的に保証して保存する。"""
        await self.save_with_conflict_map(
            MEDICATION_HISTORY_CATEGORY_CATALOG_MAPPING,
            catalog,
            conflicts={},
        )
