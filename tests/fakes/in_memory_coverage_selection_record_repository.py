"""適用資格選択履歴Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.reception.repository import CoverageSelectionRecordRepository
from app.domain.store.primitives import StoreId


class InMemoryCoverageSelectionRecordRepository(CoverageSelectionRecordRepository):
    """法人・店舗・患者境界を適用するテスト用の履歴Repository。

    履歴は ``CoverageSelection`` を丸ごと保持し、元IDとスナップショットへ
    分解して保存しない。平坦化すると枠構造による対応保証が失われるため。
    """

    def __init__(self) -> None:
        self.items: dict[CoverageSelectionRecordId, CoverageSelectionRecord] = {}

    async def save(self, record: CoverageSelectionRecord) -> None:
        """履歴をコピーして保存する。一意性制約は課さない。"""
        self.items[record.id] = copy.deepcopy(record)

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageSelectionRecord | None:
        """``(recorded_at, id)`` の降順で最新の履歴を取得する。

        記録時刻が同着でも順序が決まるよう、契約どおりIDを第2キーにする。
        """
        matched = [
            item
            for item in self.items.values()
            if item.corporate_id == corporate_id
            and item.store_id == store_id
            and item.patient_id == patient_id
        ]
        if not matched:
            return None
        latest = max(matched, key=lambda item: (item.recorded_at.value, item.id.value))
        return copy.deepcopy(latest)
