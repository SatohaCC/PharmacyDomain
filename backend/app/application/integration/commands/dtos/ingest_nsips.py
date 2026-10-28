"""Applicationのingest_nsipsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class IngestNsipsResultDto:
    """NSIPS取込結果DTO。

    保険情報の不足は情報として返す。請求用資格を自動選択しないため、
    coverage_selection_record_id は未設定で返す。
    """

    corporate_id: str
    store_id: str
    patient_id: str
    prescription_id: str | None = None
    dispensing_id: str | None = None
    medication_history_id: str | None = None
    follow_up_id: str | None = None
    document_number: str | None = None
    patient_name: str
    is_new_patient: bool
    is_duplicate: bool = False
    is_follow_up_only: bool = False
    has_pending_correction_review: bool = False
    patient_attribute_conflicts: tuple[str, ...] = ()
    patient_profile_updated_fields: tuple[str, ...] = ()
    coverage_review_required: bool = False
    coverage_review_reason: str | None = None
    coverage_selection_record_id: str | None = None
    dispensed_date: str | None = None
    addition_names: tuple[str, ...] = ()
