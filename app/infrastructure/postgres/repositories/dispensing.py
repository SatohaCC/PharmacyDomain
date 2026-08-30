"""調剤セッションの PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.dispensing.primitives import DispensingId
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.prescription.primitives import PrescriptionId
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import dispensing_processes


def row_values(process: DispensingProcess) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": process.id.value,
        "corporate_id": process.corporate_id.value,
        "store_id": process.store_id.value,
        "patient_id": process.patient_id.value,
        "prescription_id": process.prescription_id.value,
        "iteration": process.iteration.value,
        "status": process.status.value,
        "payload": encode_aggregate(process),
    }


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
        result = await self.session.execute(
            select(dispensing_processes).where(
                dispensing_processes.c.corporate_id == corporate_id.value,
                dispensing_processes.c.id == dispensing_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=dispensing_processes.name,
            )
        )

    async def list_by_prescription(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> list[DispensingProcess]:
        """処方箋に紐付く調剤セッションを回数順で返す。"""
        result = await self.session.execute(
            select(dispensing_processes)
            .where(
                dispensing_processes.c.corporate_id == corporate_id.value,
                dispensing_processes.c.prescription_id == prescription_id.value,
            )
            .order_by(dispensing_processes.c.iteration, dispensing_processes.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=dispensing_processes.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, process: DispensingProcess) -> None:
        """調剤セッションを保存し、処方箋ごとの回数重複を拒否する。"""
        try:
            await self.upsert(
                dispensing_processes,
                aggregate_id=process.id.value,
                values=row_values(process),
            )
        except IntegrityError as error:
            if (
                constraint_name(error)
                == "uq_dispensing_processes_prescription_iteration"
            ):
                raise DispensingAlreadyExistsError(
                    iteration=process.iteration.value
                ) from error
            raise


def _decode_row(row: Mapping[str, object]) -> DispensingProcess:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "調剤セッションの payload が JSON オブジェクトではありません。"
        )
    process = decode_aggregate(payload, DispensingProcess)
    if (
        process.id.value != row.get("id")
        or process.corporate_id.value != row.get("corporate_id")
        or process.store_id.value != row.get("store_id")
        or process.patient_id.value != row.get("patient_id")
        or process.prescription_id.value != row.get("prescription_id")
        or process.iteration.value != row.get("iteration")
        or process.status.value != row.get("status")
    ):
        raise PersistenceMappingError(
            "調剤セッションの検索列と payload が一致しません。"
        )
    return process
