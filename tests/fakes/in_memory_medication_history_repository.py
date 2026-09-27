"""薬歴Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
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
from app.domain.medication_history.repository import (
    FinalizedMedicationHistorySource,
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
)
from app.domain.medication_history.services import MedicationHistoryUniquenessService
from app.domain.patient.primitives import PatientId


class InMemoryMedicationHistoryRepository(MedicationHistoryRepository):
    """法人境界を適用するテスト用薬歴Repository。"""

    def __init__(self) -> None:
        self.items: dict[MedicationHistoryRecordId, MedicationHistoryRecord] = {}
        self.get_calls = 0

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """指定法人の薬歴だけを取得する。"""
        self.get_calls += 1
        item = self.items.get(record_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def get_by_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> MedicationHistoryRecord | None:
        """調剤セッションに紐付く確定済の薬歴を返す。"""
        for item in self.items.values():
            if (
                item.corporate_id == corporate_id
                and item.dispensing_id == dispensing_id
                and item.is_finalized
            ):
                return copy.deepcopy(item)
        return None

    async def get_legacy_report_target(
        self,
        *,
        corporate_id: CorporateId,
        legacy_parent_record_id: MedicationHistoryRecordId,
        tracing_report_id: str,
    ) -> MedicationHistoryRecordId | None:
        del corporate_id, legacy_parent_record_id, tracing_report_id
        return None

    async def get_by_event(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> MedicationHistoryRecord | None:
        """指定Eventの薬歴を、同じ法人に属する場合だけ返す。"""
        for item in self.items.values():
            if item.corporate_id == corporate_id and item.event_id == event_id:
                return copy.deepcopy(item)
        return None

    async def get_finalized_source_for_follow_up(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> FinalizedMedicationHistorySource | None:
        """確定済みなら、本文を含まないフォローアップ参照を返す。"""
        item = self.items.get(record_id)
        if (
            item is None
            or item.corporate_id != corporate_id
            or item.status is not MedicationHistoryStatus.FINALIZED
        ):
            return None
        return FinalizedMedicationHistorySource(
            event_id=item.event_id,
            patient_id=item.patient_id,
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴を本番Repositoryと同じ昇順で返す。"""
        matched = [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]
        return _sort_timeline(matched)

    async def list_for_profile_projection(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> list[MedicationHistoryRecord]:
        """頭書き再投影用の全店舗記録を返す。"""
        return _sort_timeline(
            [
                copy.deepcopy(item)
                for item in self.items.values()
                if item.corporate_id == corporate_id and item.patient_id == patient_id
            ]
        )

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。

        Applicationの事前readは早期エラー用であり原子性の代替ではないため、
        Repository契約として保存の直前にも同じ判定を行う。判定は
        ``MedicationHistoryUniquenessService`` を呼び、規則の実装が2箇所に
        分かれないようにする。
        """
        MedicationHistoryUniquenessService().ensure_no_conflict(
            record,
            [item for item in self.items.values() if item.id != record.id],
        )
        if any(
            item.id != record.id and item.event_id == record.event_id
            for item in self.items.values()
        ):
            raise MedicationHistoryAlreadyExistsError()
        self.items[record.id] = copy.deepcopy(record)


class InMemoryMedicationHistoryCategoryCatalogRepository(
    MedicationHistoryCategoryCatalogRepository
):
    """法人別薬歴記載区分カタログRepositoryのインメモリ実装。"""

    def __init__(self) -> None:
        self.items: dict[CorporateId, MedicationHistoryCategoryCatalog] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
    ) -> MedicationHistoryCategoryCatalog | None:
        """指定法人の区分カタログを取得する。"""
        item = self.items.get(corporate_id)
        if item is None:
            return None
        return copy.deepcopy(item)

    async def save(self, catalog: MedicationHistoryCategoryCatalog) -> None:
        """法人の区分カタログを保存する。"""
        self.items[catalog.corporate_id] = copy.deepcopy(catalog)


def _sort_timeline(
    records: list[MedicationHistoryRecord],
) -> list[MedicationHistoryRecord]:
    """確定順・監査時刻・薬歴IDで時系列を決定する。"""
    maximum = datetime.max.replace(tzinfo=UTC)

    def key(
        record: MedicationHistoryRecord,
    ) -> tuple[bool, bool, datetime, bool, datetime, str]:
        effective_counseled_at = record.effective_facts.counseled_at
        counseled_at = (
            effective_counseled_at.value
            if effective_counseled_at is not None
            else maximum
        )
        audit_at = (
            record.finalized_at.value
            if record.finalized_at is not None
            else record.recorded_at.value
            if record.recorded_at is not None
            else maximum
        )
        return (
            not record.is_projection_eligible,
            record.counseled_at is None,
            counseled_at,
            record.finalized_at is None and record.recorded_at is None,
            audit_at,
            str(record.id.value),
        )

    return sorted(records, key=key)
