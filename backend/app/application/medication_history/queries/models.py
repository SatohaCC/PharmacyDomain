"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.common.pagination import DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class GetMedicationHistoryQuery:
    """薬歴取得の入力データ。"""

    corporate_id: str
    record_id: str


@dataclass(frozen=True, kw_only=True)
class GetFollowUpSourceQuery:
    """確定済み薬歴をフォローアップの関連元として解決する入力。"""

    corporate_id: str
    record_id: str


@dataclass(frozen=True, kw_only=True)
class ListMedicationHistoriesQuery:
    """患者の薬歴タイムライン取得の入力データ。"""

    corporate_id: str
    patient_id: str


@dataclass(frozen=True, kw_only=True)
class GetMedicationHistoryViewQuery:
    """薬歴と現行患者プロフィールの表示用読取条件。"""

    corporate_id: str
    record_id: str


@dataclass(frozen=True, kw_only=True)
class GetPatientMedicalProfileQuery:
    """頭書き取得の入力データ。"""

    corporate_id: str
    patient_id: str
    as_of: date


@dataclass(frozen=True, kw_only=True)
class ListPendingExternalCorrectionsQuery:
    """外部訂正の未完了一覧検索条件。"""

    corporate_id: str
    store_id: str | None = None
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_SIZE
    status: str | None = None


@dataclass(frozen=True, kw_only=True)
class VerifyStatutoryRecordQuery:
    """調剤録代替の確認の入力データ。"""

    corporate_id: str
    record_id: str
