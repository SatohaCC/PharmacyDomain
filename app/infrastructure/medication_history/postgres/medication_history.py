"""薬歴集約の PostgreSQL Repository。

下書きは同じ調剤セッションに何件あってもよく、確定済だけが1件に制限される。
一意性を課すのは確定済の行だけなので、最終防衛は部分一意インデックスになる。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import (
    Date,
    and_,
    case,
    delete,
    func,
    literal,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.sql import cast as sql_cast

from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.exceptions import ConcurrentModificationError
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
    MedicationHistoryExternalCorrectionMatch,
    MedicationHistoryRepository,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionStatus,
)
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
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
            self._restore(
                MEDICATION_HISTORY_RECORD_MAPPING,
                cast(Mapping[str, object], row),
            )
            for row in result.mappings().all()
        ]
        return _sort_timeline(records)

    async def update_retention_expiry_dates(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        expiry_dates: Mapping[MedicationHistoryRecordId, date],
    ) -> None:
        """法人・患者内の指定行で期限JSONだけを楽観ロック付きで延長する。"""
        table = medication_history_records
        for record_id, expiry_date in expiry_dates.items():
            expected_version = self._unit_of_work.loaded_version(
                record_id.value,
                namespace=table.name,
            )
            if expected_version is None:
                raise ConcurrentModificationError()

            stored_expiry = table.c.payload["retention_expiry_date"].astext
            result = await self.session.execute(
                update(table)
                .where(
                    table.c.id == record_id.value,
                    table.c.corporate_id == corporate_id.value,
                    table.c.patient_id == patient_id.value,
                    table.c.status == MedicationHistoryStatus.FINALIZED.value,
                    table.c.version == expected_version,
                    or_(
                        stored_expiry.is_(None),
                        sql_cast(stored_expiry, Date) < expiry_date,
                    ),
                )
                .values(
                    payload=table.c.payload.op("||")(
                        func.jsonb_build_object(
                            literal("retention_expiry_date"),
                            literal(expiry_date.isoformat()),
                        )
                    ),
                    version=expected_version + 1,
                    updated_at=func.now(),
                )
                .returning(table.c.version, table.c.store_id)
            )
            row = result.mappings().one_or_none()
            if row is None:
                raise ConcurrentModificationError()
            version = row["version"]
            store_id = row["store_id"]
            if not isinstance(version, int) or not isinstance(store_id, UUID):
                raise RuntimeError("保存期限更新の返却値が不正です。")
            self._unit_of_work.record_version(
                record_id.value,
                version,
                namespace=table.name,
            )
            self._unit_of_work.pending_changes.append(
                (
                    "medication_history_records.update_retention_expiry",
                    record_id.value,
                    corporate_id.value,
                    store_id,
                )
            )

    async def list_external_corrections(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId | None,
        statuses: tuple[ExternalCorrectionStatus, ...],
        after: tuple[str, str] | None,
        limit: int,
    ) -> list[MedicationHistoryExternalCorrectionMatch]:
        """JSONB展開後に法人・店舗・状態・複合cursorをDBで絞る。"""
        table = medication_history_records
        elements = (
            func.jsonb_array_elements(table.c.payload["external_corrections"])
            .table_valued("value")
            .lateral("external_correction")
        )
        value = sql_cast(elements.c.value, JSONB)
        status_value = func.coalesce(
            value["status"].as_string(),
            case(
                (value["acknowledged_at"].as_string().is_not(None), "resolved"),
                else_="pending",
            ),
        )
        requested_statuses = tuple(status.value for status in statuses)
        jsonpath = _correction_jsonpath(statuses)
        statement = (
            select(*table.c, value.label("external_correction"))
            .select_from(table.join(elements, true()))
            .where(
                table.c.corporate_id == corporate_id.value,
                table.c.status == MedicationHistoryStatus.FINALIZED.value,
                table.c.payload.op("@?")(sql_cast(literal(jsonpath), JSONPATH)),
                status_value.in_(requested_statuses),
            )
        )
        if store_id is not None:
            statement = statement.where(table.c.store_id == store_id.value)
        if after is not None:
            try:
                after_record_id = UUID(after[0])
            except ValueError as exc:
                raise ValueError("一覧cursorの薬歴IDが不正です。") from exc
            correction_id_value = value["correction_id"].as_string()
            statement = statement.where(
                or_(
                    table.c.id > after_record_id,
                    and_(
                        table.c.id == after_record_id,
                        correction_id_value > after[1],
                    ),
                )
            )
        statement = statement.order_by(
            table.c.id, value["correction_id"].as_string()
        ).limit(limit)
        result = await self.session.execute(statement)
        matches: list[MedicationHistoryExternalCorrectionMatch] = []
        for row in result.mappings().all():
            record = MEDICATION_HISTORY_RECORD_MAPPING.decode(
                cast(Mapping[str, object], row)
            )
            raw_correction = row["external_correction"]
            correction_id = cast(dict[str, object], raw_correction).get("correction_id")
            correction = next(
                (
                    item
                    for item in record.external_corrections
                    if item.correction_id == correction_id
                ),
                None,
            )
            if correction is None:
                continue
            matches.append(
                MedicationHistoryExternalCorrectionMatch(
                    record=record, correction=correction
                )
            )
        return matches

    async def delete_unperformed_draft(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> bool:
        """未指導・未確定DRAFTを条件付きDELETEで破棄する。"""
        statement = (
            delete(medication_history_records)
            .where(
                medication_history_records.c.id == record_id.value,
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.status
                == MedicationHistoryStatus.DRAFT.value,
                medication_history_records.c.counseled_at.is_(None),
                medication_history_records.c.payload["counselor_id"]
                .as_string()
                .is_(None),
            )
            .returning(medication_history_records.c.id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

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


def _correction_jsonpath(statuses: tuple[ExternalCorrectionStatus, ...]) -> str:
    """未移行の確認済みpayloadも含めてJSONB GINで候補を絞るpathを作る。"""
    clauses = [f'@.status == "{status.value}"' for status in statuses]
    if ExternalCorrectionStatus.PENDING in statuses:
        clauses.append("(!exists(@.status) && !exists(@.acknowledged_at))")
    if ExternalCorrectionStatus.RESOLVED in statuses:
        clauses.append("(!exists(@.status) && exists(@.acknowledged_at))")
    return "$.external_corrections[*] ? (" + " || ".join(clauses) + ")"
