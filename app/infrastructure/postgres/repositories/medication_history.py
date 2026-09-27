"""薬歴集約の PostgreSQL Repository。

下書きは同じ調剤セッションに何件あってもよく、確定済だけが1件に制限される。
一意性を課すのは確定済の行だけなので、最終防衛は部分一意インデックスになる。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select

from app.domain.care_event.primitives import EventId
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
    TracingReportId,
)
from app.domain.medication_history.repository import (
    FinalizedMedicationHistorySource,
    MedicationHistoryRepository,
)
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import (
    legacy_tracing_report_links,
    medication_history_records,
)


def _history_record_columns(record: MedicationHistoryRecord) -> dict[str, object]:
    """検索・一意性制約に使う列を薬歴から導く。"""
    counseled_at = record.effective_facts.counseled_at
    return {
        "id": record.id.value,
        "event_id": record.event_id.value,
        "corporate_id": record.corporate_id.value,
        "store_id": record.store_id.value,
        "patient_id": record.patient_id.value,
        "dispensing_id": (
            record.dispensing_id.value if record.dispensing_id is not None else None
        ),
        "prescription_id": (
            record.prescription_id.value if record.prescription_id is not None else None
        ),
        "status": record.status.value,
        "counseled_at": counseled_at.value if counseled_at is not None else None,
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
            ),
        )

    async def get_by_event(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> MedicationHistoryRecord | None:
        """Eventに関連する薬歴を法人範囲内で取得する。"""
        return await self.find_one(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.event_id == event_id.value,
            ),
        )

    async def get_finalized_source_for_follow_up(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> FinalizedMedicationHistorySource | None:
        """確定済薬歴を店舗横断で照会し、本文を読まずに関連元だけ返す。"""
        result = await self.session.execute(
            select(
                medication_history_records.c.event_id,
                medication_history_records.c.patient_id,
            ).where(
                medication_history_records.c.id == record_id.value,
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.status
                == MedicationHistoryStatus.FINALIZED.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return FinalizedMedicationHistorySource(
            event_id=EventId(row["event_id"]),
            patient_id=PatientId(row["patient_id"]),
        )

    async def get_legacy_report_target(
        self,
        *,
        corporate_id: CorporateId,
        legacy_parent_record_id: MedicationHistoryRecordId,
        tracing_report_id: str,
    ) -> MedicationHistoryRecordId | None:
        """移行前の親IDとレポートIDから、追記対象の子薬歴を返す。"""
        result = await self.session.execute(
            select(legacy_tracing_report_links.c.target_record_id).where(
                legacy_tracing_report_links.c.corporate_id == corporate_id.value,
                legacy_tracing_report_links.c.legacy_parent_record_id
                == legacy_parent_record_id.value,
                legacy_tracing_report_links.c.legacy_tracing_report_id
                == TracingReportId.parse(tracing_report_id).value,
            )
        )
        target_id = result.scalar_one_or_none()
        return MedicationHistoryRecordId(target_id) if target_id is not None else None

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを指導日時の昇順で返す。"""
        records = await self.find_all(
            MEDICATION_HISTORY_RECORD_MAPPING,
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            ),
        )
        return _sort_timeline(records)

    async def list_for_profile_projection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """頭書き投影の内部処理向けに、店舗読取範囲を越えて全履歴を読む。"""
        result = await self.session.execute(
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            )
        )
        records = [
            MEDICATION_HISTORY_RECORD_MAPPING.decode(cast(Mapping[str, object], row))
            for row in result.mappings().all()
        ]
        return _sort_timeline(records)

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。"""
        await self.save_with_conflict_map(
            MEDICATION_HISTORY_RECORD_MAPPING,
            record,
            conflicts={
                "uq_medication_history_records_finalized_dispensing": MedicationHistoryAlreadyExistsError,
                "uq_medication_history_records_event": MedicationHistoryAlreadyExistsError,
            },
        )


def _sort_timeline(
    records: list[MedicationHistoryRecord],
) -> list[MedicationHistoryRecord]:
    """指導日時、監査日時、薬歴IDで昇順に固定する。下書きは最後に置く。"""
    maximum = datetime.max.replace(tzinfo=UTC)

    def key(
        record: MedicationHistoryRecord,
    ) -> tuple[bool, bool, datetime, bool, datetime, str]:
        effective_time = record.effective_facts.counseled_at
        counseled_at = effective_time.value if effective_time is not None else maximum
        audit_at = (
            record.finalized_at.value
            if record.finalized_at is not None
            else record.recorded_at.value
            if record.recorded_at is not None
            else maximum
        )
        return (
            not record.is_projection_eligible,
            effective_time is None,
            counseled_at,
            record.finalized_at is None and record.recorded_at is None,
            audit_at,
            str(record.id.value),
        )

    return sorted(records, key=key)
