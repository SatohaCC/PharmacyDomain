"""薬歴指導記録集約。

本コンテキストにおける**唯一の真実の源**。頭書き（``PatientMedicalProfile``）は
この集約の列から決定的に再構築できる投影であり、独立した真実を持たない。

**集約が単独で検証できることだけを ``validate()`` に置く。** 指導した薬剤師の
資格は Staff 集約が持ち、調剤セッションとの患者一致は Dispensing 集約が持つ。
これらは Domain Service が担う。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.exceptions import (
    DuplicatedFollowUpIdError,
    DuplicatedTracingReportIdError,
    FinalizationDateBeforeCounselingError,
    FinalizationDelayReasonRequiredError,
    FinalizationStaffRequiredError,
    FollowUpDateBeforeCounselingError,
    FollowUpNotFoundError,
    FollowUpOnDraftError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    SoapContentRequiredError,
    TracingReportAlreadyRespondedError,
    TracingReportDateBeforeCounselingError,
    TracingReportDateBeforeFollowUpError,
    TracingReportNotFoundError,
    TracingReportOnDraftError,
    TracingReportResponseDateBeforeProvidedError,
)
from app.domain.medication_history.primitives import (
    AmendmentReason,
    AmendmentTimestamp,
    CounselingMethod,
    CounselingTimestamp,
    ExternalCorrectionTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
    TracingReportId,
)
from app.domain.medication_history.value_objects import (
    CategorizedNote,
    ExternalPrescriptionCorrection,
    FollowUpRecord,
    HandbookStatus,
    MedicationHistoryAmendment,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
    TracingReport,
    TracingReportResponse,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.shared.preservation import PreservationPolicyCatalog
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryRecord(AggregateRoot[MedicationHistoryRecordId]):
    """1回の服薬指導の記録を管理する集約ルート。"""

    id: MedicationHistoryRecordId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    dispensing_id: DispensingId
    prescription_id: PrescriptionId
    counselor_id: StaffId
    counseled_at: CounselingTimestamp
    method: CounselingMethod
    soap: SoapRecord
    handbook_status: HandbookStatus
    #: 法定記載事項ウ（ホ）が「残薬がないときは、その旨を記載すること」と定めるため必須。
    residual_drug: ResidualDrugRecord
    information_sheet_provided: bool = False
    # 別モジュールの frozen dataclass なので ruff が不変性を追えない（RUF009）。
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()
    status: MedicationHistoryStatus = MedicationHistoryStatus.DRAFT
    amendments: tuple[MedicationHistoryAmendment, ...] = ()
    follow_ups: tuple[FollowUpRecord, ...] = ()
    tracing_reports: tuple[TracingReport, ...] = ()
    finalized_at: FinalizedTimestamp | None = None
    finalized_by: StaffId | None = None
    delay_reason: FinalizationDelayReason | None = None
    retention_expiry_date: date | None = None
    external_corrections: tuple[ExternalPrescriptionCorrection, ...] = ()

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """薬歴が単独で判定できる不変条件を検証する。

        SOAP の充足は**確定済のときだけ**課す。下書きの途中で
        全セクションを要求すると、聞き取りながら書き足す運用ができない。
        """
        self._ensure_amendments_only_after_finalized()
        self._ensure_finalized_soap_is_complete()
        self._ensure_finalization_metadata_is_valid()

    def _ensure_amendments_only_after_finalized(self) -> None:
        """追記が確定済の薬歴にだけ付くことを検証する。"""
        if self.amendments and not self.status.is_finalized:
            raise MedicationHistoryNotFinalizedError()

    def _ensure_finalized_soap_is_complete(self) -> None:
        """確定済の薬歴に、服薬指導等の記載が1件以上あることを検証する。

        S/O/A/Pの全4節画一的強制は行わないが、SOAPおよび追加記載メモの
        双方が空である白紙の確定は拒否する。
        """
        if not self.status.is_finalized:
            return
        has_soap = self.effective_soap.has_content
        has_additional = any(note.has_content for note in self.additional_notes)
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()

    def _ensure_finalization_metadata_is_valid(self) -> None:
        """確定メタデータと真正性を検証する。"""
        if self.status.is_finalized:
            if self.finalized_at is None or self.finalized_by is None:
                raise FinalizationStaffRequiredError()
            if self.finalized_at.value < self.counseled_at.value:
                raise FinalizationDateBeforeCounselingError()
            if (
                self.finalized_at.value.date() != self.counseled_at.value.date()
                and self.delay_reason is None
            ):
                raise FinalizationDelayReasonRequiredError()
        else:
            if (
                self.finalized_at is not None
                or self.finalized_by is not None
                or self.delay_reason is not None
            ):
                raise MedicationHistoryDomainError(
                    "下書き状態の薬歴に確定メタデータは設定できません。"
                )

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        """確定済か。"""
        return self.status.is_finalized

    @property
    def effective_soap(self) -> SoapRecord:
        """現時点で有効なSOAP。追記があれば最後の追記の内容。

        元の記録を書き換えないので、``soap`` は交付時のまま残る。
        """
        if not self.amendments:
            return self.soap
        return self.amendments[-1].amended_soap

    @property
    def updates_profile(self) -> bool:
        """この薬歴が頭書きへ差分を持つか。"""
        return not self.profile_updates.is_empty

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        dispensing_id: DispensingId,
        prescription_id: PrescriptionId,
        counselor_id: StaffId,
        counseled_at: CounselingTimestamp,
        method: CounselingMethod,
        soap: SoapRecord,
        handbook_status: HandbookStatus,
        residual_drug: ResidualDrugRecord,
        information_sheet_provided: bool = False,
        profile_updates: ProfileUpdateIntents | None = None,
        additional_notes: tuple[CategorizedNote, ...] = (),
    ) -> Self:
        """服薬指導の記録を下書きとして起こす。"""
        return cls(
            id=MedicationHistoryRecordId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            method=method,
            soap=soap,
            handbook_status=handbook_status,
            residual_drug=residual_drug,
            information_sheet_provided=information_sheet_provided,
            profile_updates=(
                profile_updates
                if profile_updates is not None
                else ProfileUpdateIntents()
            ),
            additional_notes=additional_notes,
            status=MedicationHistoryStatus.DRAFT,
        )

    # ------------------------------------------------------------------
    # 編集と確定
    # ------------------------------------------------------------------

    def update_draft_soap(self, soap: SoapRecord) -> Self:
        """下書きのSOAPを差し替える。

        確定済の薬歴は受け付けない。修正は :meth:`amend` による追記のみ。
        """
        self._ensure_not_finalized()
        return replace(self, soap=soap)

    def update_draft_profile_updates(self, intents: ProfileUpdateIntents) -> Self:
        """下書きの頭書き差分を差し替える。"""
        self._ensure_not_finalized()
        return replace(self, profile_updates=intents)

    def update_draft(
        self,
        *,
        method: CounselingMethod | None = None,
        soap: SoapRecord | None = None,
        handbook_status: HandbookStatus | None = None,
        residual_drug: ResidualDrugRecord | None = None,
        information_sheet_provided: bool | None = None,
        profile_updates: ProfileUpdateIntents | None = None,
        additional_notes: tuple[CategorizedNote, ...] | None = None,
    ) -> Self:
        """下書きの全項目を差し替える。

        確定済の薬歴は受け付けない。修正は :meth:`amend` による追記のみ。
        """
        self._ensure_not_finalized()
        return replace(
            self,
            method=method if method is not None else self.method,
            soap=soap if soap is not None else self.soap,
            handbook_status=handbook_status
            if handbook_status is not None
            else self.handbook_status,
            residual_drug=residual_drug
            if residual_drug is not None
            else self.residual_drug,
            information_sheet_provided=information_sheet_provided
            if information_sheet_provided is not None
            else self.information_sheet_provided,
            profile_updates=profile_updates
            if profile_updates is not None
            else self.profile_updates,
            additional_notes=additional_notes
            if additional_notes is not None
            else self.additional_notes,
        )

    def finalize(
        self,
        *,
        finalized_at: FinalizedTimestamp | None = None,
        finalized_by: StaffId | None = None,
        delay_reason: FinalizationDelayReason | None = None,
    ) -> Self:
        """薬歴を確定する。

        確定日時・確定者の指定を必須とする。引数省略時は既存テスト互換のため、
        指導日時の当日確定（指導者と同一薬剤師）として自動補填する。
        """
        self._ensure_not_finalized()
        actual_finalized_at = (
            finalized_at
            if finalized_at is not None
            else FinalizedTimestamp(self.counseled_at.value)
        )
        actual_finalized_by = (
            finalized_by if finalized_by is not None else self.counselor_id
        )
        return replace(
            self,
            status=MedicationHistoryStatus.FINALIZED,
            finalized_at=actual_finalized_at,
            finalized_by=actual_finalized_by,
            delay_reason=delay_reason,
        )

    def amend(
        self,
        *,
        amended_soap: SoapRecord,
        reason: AmendmentReason,
        amended_by: StaffId,
        amended_at: AmendmentTimestamp,
    ) -> Self:
        """確定済の薬歴に修正を**追記**する。

        元の ``soap`` は書き換えない。調剤録は3年間の保存義務があり、
        遡って書き換えられる記録は監査に耐えない。

        Raises:
            MedicationHistoryNotFinalizedError: 未確定の薬歴である場合。
            SoapSectionEmptyError: 追記後の実効SOAPに記載の無いセクションが
                できる場合。確定時に課した充足を追記で抜けられないようにする。
        """
        if not self.is_finalized:
            raise MedicationHistoryNotFinalizedError()
        amendment = MedicationHistoryAmendment(
            amended_soap=amended_soap,
            reason=reason,
            amended_by=amended_by,
            amended_at=amended_at,
        )
        return replace(self, amendments=(*self.amendments, amendment))

    def _ensure_not_finalized(self) -> None:
        """確定済でないことを保証する。"""
        if self.is_finalized:
            raise MedicationHistoryAlreadyFinalizedError()

    def add_follow_up(self, follow_up: FollowUpRecord) -> Self:
        """確定済の薬歴に服薬期間中フォローアップ記録を追加する。

        Raises:
            FollowUpOnDraftError: 薬歴が未確定（下書き）の場合。
            FollowUpDateBeforeCounselingError: 初回指導日時より前のフォローアップ日時の場合。
            DuplicatedFollowUpIdError: 同一のフォローアップIDが既に存在する場合。
        """
        if not self.is_finalized:
            raise FollowUpOnDraftError()
        if follow_up.followed_up_at.value < self.counseled_at.value:
            raise FollowUpDateBeforeCounselingError()
        if any(existing.id == follow_up.id for existing in self.follow_ups):
            raise DuplicatedFollowUpIdError()
        return replace(self, follow_ups=(*self.follow_ups, follow_up))

    def add_tracing_report(self, report: TracingReport) -> Self:
        """確定済の薬歴に処方医へのトレーシングレポート提供記録を追加する。

        Raises:
            TracingReportOnDraftError: 薬歴が未確定（下書き）の場合。
            TracingReportDateBeforeCounselingError: 初回指導日時より前の提供日時の場合。
            FollowUpNotFoundError: 指定されたフォローアップIDが存在しない場合。
            TracingReportDateBeforeFollowUpError: 紐付けられたフォローアップ日時より前の提供日時の場合。
            DuplicatedTracingReportIdError: 同一のレポートIDが既に存在する場合。
        """
        if not self.is_finalized:
            raise TracingReportOnDraftError()
        if report.provided_at.value < self.counseled_at.value:
            raise TracingReportDateBeforeCounselingError()
        if report.follow_up_id is not None:
            matching_follow_up = next(
                (fu for fu in self.follow_ups if fu.id == report.follow_up_id), None
            )
            if matching_follow_up is None:
                raise FollowUpNotFoundError()
            if report.provided_at.value < matching_follow_up.followed_up_at.value:
                raise TracingReportDateBeforeFollowUpError()
        if any(existing.id == report.id for existing in self.tracing_reports):
            raise DuplicatedTracingReportIdError()
        return replace(self, tracing_reports=(*self.tracing_reports, report))

    def record_tracing_report_response(
        self,
        tracing_report_id: TracingReportId,
        response: TracingReportResponse,
    ) -> Self:
        """トレーシングレポートに対する処方医からの返答を記録する。

        Raises:
            TracingReportNotFoundError: 指定されたレポートIDが存在しない場合。
            TracingReportAlreadyRespondedError: 既に返答が記録されている場合。
            TracingReportResponseDateBeforeProvidedError: 提供日時より前の返答日時の場合。
        """
        report = next(
            (r for r in self.tracing_reports if r.id == tracing_report_id), None
        )
        if report is None:
            raise TracingReportNotFoundError()
        if report.response is not None:
            raise TracingReportAlreadyRespondedError()
        if response.responded_at.value < report.provided_at.value:
            raise TracingReportResponseDateBeforeProvidedError()
        updated_report = replace(report, response=response)
        updated_reports = tuple(
            updated_report if r.id == tracing_report_id else r
            for r in self.tracing_reports
        )
        return replace(self, tracing_reports=updated_reports)

    @property
    def has_pending_correction_review(self) -> bool:
        """未確認の外部処方訂正が存在するか。"""
        return any(not c.is_acknowledged for c in self.external_corrections)

    def record_external_correction(
        self, correction: ExternalPrescriptionCorrection
    ) -> Self:
        """確定済みの記録を壊さず外部処方訂正を追記する。

        確定済み薬歴の原本（SOAP・確定日時・確定者）は真正性保護のため不可逆凍結し、
        外部から発生した処方変更・調剤訂正の事実を本証跡として記録する。
        """
        return replace(
            self, external_corrections=(*self.external_corrections, correction)
        )

    def acknowledge_external_correction(
        self,
        *,
        correction_id: str,
        acknowledged_by: StaffId,
        acknowledged_at: ExternalCorrectionTimestamp,
    ) -> Self:
        """外部処方訂正を薬剤師が確認したことを記録する。"""
        target = next(
            (c for c in self.external_corrections if c.correction_id == correction_id),
            None,
        )
        if target is None:
            raise MedicationHistoryDomainError("指定された外部訂正IDが存在しません。")
        updated_correction = replace(
            target,
            acknowledged_by=acknowledged_by,
            acknowledged_at=acknowledged_at,
        )
        updated_corrections = tuple(
            updated_correction if c.correction_id == correction_id else c
            for c in self.external_corrections
        )
        return replace(self, external_corrections=updated_corrections)

    def calculate_and_set_retention_expiry(
        self, catalog: PreservationPolicyCatalog
    ) -> Self:
        """保存期間ポリシーに基づいて法定保存満了日を設定する。"""
        base_date = self.counseled_at.value.date()
        expiry_date = catalog.calculate_expiry_date(base_date)
        return replace(self, retention_expiry_date=expiry_date)
