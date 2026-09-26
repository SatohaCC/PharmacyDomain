"""薬歴集約の PostgreSQL Repository。

下書きは同じ調剤セッションに何件あってもよく、確定済だけが1件に制限される。
一意性を課すのは確定済の行だけなので、最終防衛は部分一意インデックスになる。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select

from app.application.medication_history.reference import (
    MedicationHistoryFollowUpSource,
    MedicationHistoryFollowUpSourceBoundary,
)
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
    MedicationHistoryRecordKind,
    MedicationHistoryStatus,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
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
        "record_kind": record.record_kind.value,
        "source_record_id": (
            record.source_record_id.value
            if record.source_record_id is not None
            else None
        ),
        "counseled_at": (
            record.counseled_at.value if record.counseled_at is not None else None
        ),
        "recorded_at": (
            record.recorded_at.value if record.recorded_at is not None else None
        ),
    }


MEDICATION_HISTORY_RECORD_MAPPING = AggregateMapping(
    table=medication_history_records,
    aggregate_type=MedicationHistoryRecord,
    label="薬歴",
    search_columns=_history_record_columns,
)


class PostgresMedicationHistoryRepository(
    PostgresRepositoryBase,
    MedicationHistoryRepository,
    MedicationHistoryFollowUpSourceBoundary,
):
    """薬歴集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """法人境界を含めてIDで薬歴を検索する。"""
        return await self.get_by_id(
            MEDICATION_HISTORY_RECORD_MAPPING, record_id, corporate_id=corporate_id
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
                medication_history_records.c.record_kind
                == MedicationHistoryRecordKind.INITIAL.value,
            ),
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを実施・登録時刻の降順で返す。"""
        return await self.find_all(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records)
            .where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            )
            .order_by(
                medication_history_records.c.counseled_at.desc().nulls_last(),
                medication_history_records.c.recorded_at.desc().nulls_last(),
                medication_history_records.c.id.desc(),
            ),
        )

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。"""
        await self.save_with_conflict_map(
            MEDICATION_HISTORY_RECORD_MAPPING,
            record,
            conflicts={
                "uq_medication_history_records_finalized_dispensing": MedicationHistoryAlreadyExistsError,
            },
        )

    async def get_source_reference(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryFollowUpSource | None:
        """店舗読取範囲を越える本文を読まず、指定薬歴の参照メタデータを取る。"""
        result = await self.session.execute(
            select(
                medication_history_records.c.id,
                medication_history_records.c.corporate_id,
                medication_history_records.c.patient_id,
                medication_history_records.c.store_id,
                medication_history_records.c.dispensing_id,
                medication_history_records.c.prescription_id,
                medication_history_records.c.record_kind,
                medication_history_records.c.source_record_id,
                medication_history_records.c.status,
                medication_history_records.c.counseled_at,
            ).where(
                medication_history_records.c.id == record_id.value,
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            )
        )
        row = result.mappings().one_or_none()
        return (
            _follow_up_source_from_row(cast(Mapping[str, Any], row))
            if row is not None
            else None
        )

    async def list_confirmed_sources(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> tuple[MedicationHistoryFollowUpSource, ...]:
        """指定患者の確定済み参照候補を本文なしで新しい順に列挙する。"""
        result = await self.session.execute(
            select(
                medication_history_records.c.id,
                medication_history_records.c.corporate_id,
                medication_history_records.c.patient_id,
                medication_history_records.c.store_id,
                medication_history_records.c.dispensing_id,
                medication_history_records.c.prescription_id,
                medication_history_records.c.record_kind,
                medication_history_records.c.source_record_id,
                medication_history_records.c.status,
                medication_history_records.c.counseled_at,
            )
            .where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
                medication_history_records.c.status
                == MedicationHistoryStatus.FINALIZED.value,
                medication_history_records.c.counseled_at.is_not(None),
            )
            .order_by(
                medication_history_records.c.counseled_at.desc(),
                medication_history_records.c.id.desc(),
            )
        )
        return tuple(
            _follow_up_source_from_row(cast(Mapping[str, Any], row))
            for row in result.mappings().all()
        )


def _follow_up_source_from_row(
    row: Mapping[str, Any],
) -> MedicationHistoryFollowUpSource:
    """payload列を含まない行を値オブジェクトへ変換する。"""
    raw_source_id = row["source_record_id"]
    raw_counseled_at = row["counseled_at"]
    return MedicationHistoryFollowUpSource(
        record_id=MedicationHistoryRecordId.parse(str(row["id"])),
        corporate_id=CorporateId.parse(str(row["corporate_id"])),
        patient_id=PatientId.parse(str(row["patient_id"])),
        store_id=StoreId.parse(str(row["store_id"])),
        dispensing_id=DispensingId.parse(str(row["dispensing_id"])),
        prescription_id=PrescriptionId.parse(str(row["prescription_id"])),
        record_kind=MedicationHistoryRecordKind(str(row["record_kind"])),
        source_record_id=(
            MedicationHistoryRecordId.parse(str(raw_source_id))
            if raw_source_id is not None
            else None
        ),
        status=MedicationHistoryStatus(str(row["status"])),
        counseled_at=(
            cast(datetime, raw_counseled_at) if raw_counseled_at is not None else None
        ),
    )
