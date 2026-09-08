"""調剤セッション集約の PostgreSQL Repository。

同じ処方箋の同じ回数（リフィルの何回目か）は1件しか存在できない。回数は
処方箋IDと組で一意なので、最終防衛は組の一意制約になる。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.dispensing.primitives import DispensingId
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.prescription.primitives import PrescriptionId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import dispensing_processes


def _dispensing_columns(process: DispensingProcess) -> dict[str, object]:
    """検索・一意性制約に使う列を調剤セッションから導く。"""
    return {
        "id": process.id.value,
        "corporate_id": process.corporate_id.value,
        "store_id": process.store_id.value,
        "patient_id": process.patient_id.value,
        "prescription_id": process.prescription_id.value,
        "iteration": process.iteration.value,
        "status": process.status.value,
    }


DISPENSING_PROCESS_MAPPING = AggregateMapping(
    table=dispensing_processes,
    aggregate_type=DispensingProcess,
    label="調剤セッション",
    search_columns=_dispensing_columns,
)


class PostgresDispensingProcessRepository(
    PostgresRepositoryBase, DispensingProcessRepository
):
    """調剤セッション集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess | None:
        """法人境界を含めてIDで調剤セッションを検索する。"""
        return await self.get_by_id(
            DISPENSING_PROCESS_MAPPING, dispensing_id, corporate_id=corporate_id
        )

    async def list_by_prescription(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> list[DispensingProcess]:
        """処方箋に紐付く調剤セッションを回数順で返す。"""
        return await self.find_all(
            DISPENSING_PROCESS_MAPPING,
            select(dispensing_processes)
            .where(
                dispensing_processes.c.corporate_id == corporate_id.value,
                dispensing_processes.c.prescription_id == prescription_id.value,
            )
            .order_by(dispensing_processes.c.iteration, dispensing_processes.c.id),
        )

    async def save(self, process: DispensingProcess) -> None:
        """調剤セッションを保存し、処方箋ごとの回数重複を拒否する。"""
        await self.save_with_conflict_map(
            DISPENSING_PROCESS_MAPPING,
            process,
            conflicts={
                "uq_dispensing_processes_prescription_iteration": lambda: (
                    DispensingAlreadyExistsError(iteration=process.iteration.value)
                ),
            },
        )
