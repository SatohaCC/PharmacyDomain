"""薬歴Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryRecordKind,
)
from app.domain.medication_history.repository import (
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
                and item.record_kind is MedicationHistoryRecordKind.INITIAL
            ):
                return copy.deepcopy(item)
        return None

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """指導日時・登録日時・IDの降順で患者の薬歴を返す。"""
        matched = [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]
        return sorted(
            matched,
            key=lambda item: (
                item.counseled_at is not None,
                item.counseled_at.value
                if item.counseled_at is not None
                else datetime.min.replace(tzinfo=UTC),
                item.recorded_at is not None,
                item.recorded_at.value
                if item.recorded_at is not None
                else datetime.min.replace(tzinfo=UTC),
                item.id.value,
            ),
            reverse=True,
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
