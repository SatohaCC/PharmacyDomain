"""Applicationのreferencesを定義する。"""

from __future__ import annotations

from typing import Protocol

from app.application.reception.values import MedicationHistoryAssociationReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId


class MedicationHistoryAssociationBoundary(Protocol):
    """薬歴集約を保持せず、受付との関連に必要な識別情報を返す境界。"""

    async def get_for_association(
        self, *, corporate_id: CorporateId, record_id: MedicationHistoryRecordId
    ) -> MedicationHistoryAssociationReference | None:
        """法人境界を適用し、指定薬歴の関連確認用情報を返す。"""
        ...
