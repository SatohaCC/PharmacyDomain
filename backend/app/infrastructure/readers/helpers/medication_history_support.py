"""Applicationのmedication_history_supportを定義する。"""

from __future__ import annotations

from app.application.medication_history.errors import MedicationHistoryNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import MedicationHistoryRecord
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import MedicationHistoryRepository


async def load_record_or_raise(
    repository: MedicationHistoryRepository,
    *,
    corporate_id: CorporateId,
    record_id: MedicationHistoryRecordId,
) -> MedicationHistoryRecord:
    """指定法人の薬歴を取得し、存在しなければ404相当を送出する。"""
    record = await repository.get(corporate_id=corporate_id, record_id=record_id)
    if record is None:
        raise MedicationHistoryNotFoundError()
    return record
