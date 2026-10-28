"""Applicationのlist_pending_external_correctionsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PendingExternalCorrectionDto:
    """未完了の外部訂正と薬歴参照情報。"""

    record_id: str
    corporate_id: str
    store_id: str
    patient_id: str
    correction_id: str
    correction_kind: str
    correction_status: str
    source_document_number: str
    reason: str
    details: str | None
    corrected_at: str
    review_events: tuple[dict[str, str | None], ...]
