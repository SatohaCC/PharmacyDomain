"""薬歴・頭書きのリポジトリインターフェース。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
)
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class FinalizedMedicationHistorySource:
    """別店舗のフォローアップに関連付けるための最小参照。"""

    event_id: EventId
    patient_id: PatientId


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryExternalCorrectionMatch:
    """検索条件に一致した外部訂正と、その帰属薬歴。"""

    record: MedicationHistoryRecord
    correction: ExternalPrescriptionCorrection


class MedicationHistoryRepository(Protocol):
    """薬歴指導記録集約を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """指定法人の薬歴を取得する。

        他法人の薬歴は存在を隠すため ``None`` を返す（403ではなく404相当）。
        """
        ...

    async def get_by_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> MedicationHistoryRecord | None:
        """調剤セッションに紐付く確定済薬歴を取得する。"""
        ...

    async def get_by_event(
        self, *, corporate_id: CorporateId, event_id: EventId
    ) -> MedicationHistoryRecord | None:
        """Eventに関連する薬歴を取得する。Eventごとに最大1件。"""
        ...

    async def get_finalized_source_for_follow_up(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> FinalizedMedicationHistorySource | None:
        """同一法人の確定済薬歴から、関連Eventと患者だけを店舗横断で返す。"""
        ...

    async def get_legacy_report_target(
        self,
        *,
        corporate_id: CorporateId,
        legacy_parent_record_id: MedicationHistoryRecordId,
        tracing_report_id: str,
    ) -> MedicationHistoryRecordId | None:
        """旧親薬歴ID・レポートIDから移行後の帰属薬歴IDを解決する。"""
        ...

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを指導日時の昇順で返す。"""
        ...

    async def list_for_profile_projection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """頭書き再投影専用に、同一法人・患者の全店舗の記録を返す。"""
        ...

    async def update_retention_expiry_dates(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        expiry_dates: Mapping[MedicationHistoryRecordId, date],
    ) -> None:
        """同一法人・患者の指定済み薬歴で保存期限日だけを更新する。"""
        ...

    async def list_external_corrections(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId | None,
        statuses: tuple[ExternalCorrectionStatus, ...],
        after: tuple[str, str] | None,
        limit: int,
    ) -> list[MedicationHistoryExternalCorrectionMatch]:
        """法人・店舗・状態を絞り、訂正ID順で次のページを返す。"""
        ...

    async def delete_unperformed_draft(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> bool:
        """指導者・指導日時がなく未確定の薬歴だけを破棄する。"""
        ...

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同じEventまたは処方箋受付調剤の確定薬歴重複を拒否して保存する。

        同一Eventに2件目の薬歴を作らせず、調剤検索写しのある確定済記録も
        二重にしない。下書きは調剤ごとの重複を許すがEventは常に一意にする。
        Applicationの事前readは早期エラー用であり原子性の代替ではない。
        """
        ...


class PatientMedicalProfileRepository(Protocol):
    """患者医療プロファイル（頭書き）集約を永続化・検索するための操作インターフェース。"""

    async def get_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile | None:
        """患者の頭書きを取得する。

        ``None`` は欠損ではなく「まだ投影されていない」を意味する。呼び出し側は
        ``PatientMedicalProfile.empty_for()`` を作ってから畳み込んでよい。
        """
        ...

    async def save(self, profile: PatientMedicalProfile) -> None:
        """患者ごとに1件であることを原子的に保証して頭書きを保存する。

        同一法人・同一 ``patient_id`` の重複を、同じ集約IDを除外した上で拒否し、
        ``PatientMedicalProfileAlreadyExistsError`` を送出する。頭書きが2件あると、
        どちらが投影結果かが決まらなくなる。

        患者との1:1関係を ``PatientMedicalProfileId`` ではなく ``patient_id`` の
        一意制約で表すのは、``PatientExternalIdentifier`` と同じ作法である。
        """
        ...


class MedicationHistoryCategoryCatalogRepository(Protocol):
    """法人別薬歴記載区分カタログを永続化・検索する操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
    ) -> MedicationHistoryCategoryCatalog | None:
        """法人の区分カタログを取得する。未作成の場合はNoneを返す。"""
        ...

    async def save(self, catalog: MedicationHistoryCategoryCatalog) -> None:
        """法人の区分カタログを保存（作成または更新）する。"""
        ...
