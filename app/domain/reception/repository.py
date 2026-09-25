"""適用資格選択履歴のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection_record import CoverageSelectionRecord
from app.domain.reception.primitives import CoverageSelectionRecordId, ReceptionId
from app.domain.reception.reception import Reception
from app.domain.store.primitives import StoreId


class CoverageSelectionRecordRepository(Protocol):
    """適用資格選択履歴を保存・検索するための操作。"""

    async def save(self, record: CoverageSelectionRecord) -> None:
        """履歴を新規保存する。複数履歴を許可し、一意性制約は課さない。"""
        ...

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: CoverageSelectionRecordId,
    ) -> CoverageSelectionRecord | None:
        """指定法人の履歴をIDで取得する。

        他法人の履歴は存在を隠すため ``None`` を返す（403ではなく404相当）。
        患者の一致までは確認しない。呼び出し側が患者IDで絞る。
        """
        ...

    async def get_latest(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
    ) -> CoverageSelectionRecord | None:
        """``(recorded_at, id)`` の降順で最新の履歴を取得する。"""
        ...


class ReceptionRepository(Protocol):
    """受付の受信基準と訂正履歴を永続化する境界。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Reception | None:
        """法人・店舗境界を含めて受付を取得する。"""
        ...

    async def save(self, reception: Reception) -> None:
        """受付の受信記録を保存する。"""
        ...
