"""薬歴Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import MedicationHistoryUniquenessService
from app.domain.patient.primitives import PatientId


class InMemoryMedicationHistoryRepository(MedicationHistoryRepository):
    """法人境界を適用するテスト用薬歴Repository。"""

    def __init__(self) -> None:
        self.items: dict[MedicationHistoryRecordId, MedicationHistoryRecord] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """指定法人の薬歴だけを取得する。"""
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

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """指定法人・患者の薬歴を ``counseled_at`` 降順で返す。"""
        matched = [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]
        return sorted(matched, key=lambda item: item.counseled_at.value, reverse=True)

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
