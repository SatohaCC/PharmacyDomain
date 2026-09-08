"""薬歴集約の PostgreSQL Repository。

下書きは同じ調剤セッションに何件あってもよく、確定済だけが1件に制限される。
一意性を課すのは確定済の行だけなので、最終防衛は部分一意インデックスになる。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    constraint_name,
)
from app.infrastructure.postgres.schema import medication_history_records


def _history_record_columns(record: MedicationHistoryRecord) -> dict[str, object]:
    """検索・一意性制約に使う列を薬歴から導く。"""
    return {
        "id": record.id.value,
        "corporate_id": record.corporate_id.value,
        "store_id": record.store_id.value,
        "patient_id": record.patient_id.value,
        "dispensing_id": record.dispensing_id.value,
        "prescription_id": record.prescription_id.value,
        "status": record.status.value,
        "counseled_at": record.counseled_at.value,
    }


MEDICATION_HISTORY_RECORD_MAPPING = AggregateMapping(
    table=medication_history_records,
    aggregate_type=MedicationHistoryRecord,
    label="薬歴",
    search_columns=_history_record_columns,
)


class PostgresMedicationHistoryRepository(
    PostgresRepositoryBase, MedicationHistoryRepository
):
    """薬歴集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """法人境界を含めてIDで薬歴を検索する。"""
        return await self.find_one(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.id == record_id.value,
            ),
        )

    async def get_by_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> MedicationHistoryRecord | None:
        """調剤セッションに紐付く確定済の薬歴を返す。

        下書きは複数あってよいので確定済だけを対象にする。確定済が1件以下で
        あることは部分一意インデックスが保証する。
        """
        return await self.find_one(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.dispensing_id == dispensing_id.value,
                medication_history_records.c.status
                == MedicationHistoryStatus.FINALIZED.value,
            ),
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを ``counseled_at`` 降順で返す。"""
        return await self.find_all(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records)
            .where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            )
            .order_by(
                medication_history_records.c.counseled_at.desc(),
                medication_history_records.c.id.desc(),
            ),
        )

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。"""
        try:
            await self.save_aggregate(MEDICATION_HISTORY_RECORD_MAPPING, record)
        except IntegrityError as error:
            if (
                constraint_name(error)
                == "uq_medication_history_records_finalized_dispensing"
            ):
                raise MedicationHistoryAlreadyExistsError() from error
            raise
