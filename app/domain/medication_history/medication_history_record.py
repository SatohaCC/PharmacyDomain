"""薬歴指導記録集約。

本コンテキストにおける**唯一の真実の源**。頭書き（``PatientMedicalProfile``）は
この集約の列から決定的に再構築できる投影であり、独立した真実を持たない。

**集約が単独で検証できることだけを ``validate()`` に置く。** 指導した薬剤師の
資格は Staff 集約が持ち、調剤セッションとの患者一致は Dispensing 集約が持つ。
これらは Domain Service が担う。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, Self, cast
from uuid import uuid5, uuid7

from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.exceptions import (
    DuplicatedTracingReportIdError,
    FinalizationDateBeforeCounselingError,
    FinalizationDelayReasonRequiredError,
    FinalizationStaffRequiredError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryUnassessedItemsError,
    SoapContentRequiredError,
    TracingReportAlreadyRespondedError,
    TracingReportDateBeforeCounselingError,
    TracingReportNotFoundError,
    TracingReportOnDraftError,
    TracingReportResponseDateBeforeProvidedError,
)
from app.domain.medication_history.fact_correction import (
    FACT_ARRAY_TYPES,
    FACT_FIELD_TYPES,
    EffectiveMedicationHistoryFacts,
    FactElement,
    MedicationHistoryFactCorrection,
)
from app.domain.medication_history.primitives import (
    AmendmentReason,
    AmendmentTimestamp,
    CounselingMethod,
    CounselingTimestamp,
    ExternalCorrectionTimestamp,
    FactCorrectionTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    MedicationHistoryImportTimestamp,
    MedicationHistoryRecordedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
    TracingReportId,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    ExternalCorrectionDecision,
    ExternalCorrectionReviewEvent,
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
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

_FACT_VALUE_ABSENT = object()


def _replace_fact_field[T](value: T, field_name: str, new_value: object) -> T:
    """宣言済み対象だけに適用する動的フィールド更新。"""
    return cast(T, replace(cast(Any, value), **{field_name: new_value}))


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryRecord(AggregateRoot[MedicationHistoryRecordId]):
    """1回の服薬指導の記録を管理する集約ルート。"""

    id: MedicationHistoryRecordId
    event_id: EventId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    dispensing_id: DispensingId | None
    prescription_id: PrescriptionId | None
    counselor_id: StaffId | None
    counseled_at: CounselingTimestamp | None
    method: CounselingMethod | None
    soap: SoapRecord
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None = None
    # 別モジュールの frozen dataclass なので ruff が不変性を追えない（RUF009）。
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()
    billing_additions: tuple[BillingAddition, ...] = ()
    source_system: MedicationHistorySourceSystem | None = None
    imported_at: MedicationHistoryImportTimestamp | None = None
    recorded_by: StaffId | None = None
    recorded_at: MedicationHistoryRecordedTimestamp | None = None
    status: MedicationHistoryStatus = MedicationHistoryStatus.DRAFT
    amendments: tuple[MedicationHistoryAmendment, ...] = ()
    tracing_reports: tuple[TracingReport, ...] = ()
    finalized_at: FinalizedTimestamp | None = None
    finalized_by: StaffId | None = None
    delay_reason: FinalizationDelayReason | None = None
    review_result: MedicationHistoryReviewResult | None = None
    retention_expiry_date: date | None = None
    external_corrections: tuple[ExternalPrescriptionCorrection, ...] = ()
    fact_corrections: tuple[MedicationHistoryFactCorrection, ...] = ()

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """薬歴が単独で判定できる不変条件を検証する。

        SOAP の充足は**確定済のときだけ**課す。下書きの途中で
        全セクションを要求すると、聞き取りながら書き足す運用ができない。
        """
        self._ensure_fact_corrections_are_valid()
        self._ensure_counseling_provenance_is_valid()
        self._ensure_amendments_only_after_finalized()
        self._ensure_finalized_soap_is_complete()
        self._ensure_finalized_review_has_authored_evidence()
        self._ensure_finalized_items_are_assessed()
        self._ensure_finalization_metadata_is_valid()

    def _ensure_finalized_items_are_assessed(self) -> None:
        """確定前に確認が必要な項目が未記録でないことを検証する。"""
        if not self.status.is_finalized:
            return
        required_items: list[tuple[str, object | None]] = [
            ("服薬指導方法", self.effective_facts.method)
        ]
        missing_items = tuple(label for label, value in required_items if value is None)
        if missing_items:
            raise MedicationHistoryUnassessedItemsError(missing_items=missing_items)

    def _ensure_finalized_review_has_authored_evidence(self) -> None:
        """新しいレビュー証跡は薬剤師自身のA/P記載を伴う。"""
        review_result = self.effective_facts.review_result
        if not self.status.is_finalized or review_result is None:
            return
        if (
            review_result
            is MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS
        ):
            return
        if not any(
            note.has_content for note in (*self.soap.assessment, *self.soap.plan)
        ):
            raise MedicationHistoryDomainError(
                "確定には薬剤師が記載したAssessmentまたはPlanが必要です。"
            )

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
        has_additional = any(
            note.has_content for note in self.effective_facts.additional_notes
        )
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()

    def _ensure_finalization_metadata_is_valid(self) -> None:
        """確定メタデータと真正性を検証する。"""
        facts = self.effective_facts
        if self.status is MedicationHistoryStatus.FINALIZED:
            if self.finalized_at is None or self.finalized_by is None:
                raise FinalizationStaffRequiredError()
            if facts.counseled_at is None or facts.counselor_id is None:
                raise MedicationHistoryDomainError(
                    "確定済の薬歴には実際の指導者と指導日時が必要です。"
                )
            if self.finalized_at.value < facts.counseled_at.value:
                raise FinalizationDateBeforeCounselingError()
            if (
                self.finalized_at.value.date() != facts.counseled_at.value.date()
                and facts.delay_reason is None
            ):
                raise FinalizationDelayReasonRequiredError()
        elif self.status is MedicationHistoryStatus.DRAFT:
            if (
                self.finalized_at is not None
                or self.finalized_by is not None
                or self.delay_reason is not None
                or self.review_result is not None
            ):
                raise MedicationHistoryDomainError(
                    "下書き状態の薬歴に確定メタデータは設定できません。"
                )
        elif (
            self.finalized_at is not None
            or self.finalized_by is not None
            or facts.delay_reason is not None
            or facts.review_result is not None
        ):
            raise MedicationHistoryDomainError("移行記録に確定監査値は設定できません。")

    def _ensure_counseling_provenance_is_valid(self) -> None:
        """指導実績と、薬剤師記載または旧NSIPS下書きの由来を検証する。"""
        facts = self.effective_facts
        has_counselor = facts.counselor_id is not None
        has_counseled_at = facts.counseled_at is not None
        if has_counselor != has_counseled_at:
            raise MedicationHistoryDomainError(
                "指導者と指導日時は両方設定するか、両方未設定にしてください。"
            )
        if has_counselor:
            return
        if self.status is not MedicationHistoryStatus.DRAFT or (
            self.recorded_by is None
            and (
                facts.source_system != MedicationHistorySourceSystem("NSIPS")
                or self.imported_at is None
            )
        ):
            raise MedicationHistoryDomainError(
                "指導実績のない下書きには薬剤師の記載者またはNSIPS取込時刻が必要です。"
            )

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        """確定済か。"""
        return self.status.is_finalized

    @property
    def is_projection_eligible(self) -> bool:
        """頭書き再構築へ含める確定済または移行済み記録か。"""
        return self.status in {
            MedicationHistoryStatus.FINALIZED,
            MedicationHistoryStatus.LEGACY_RECORDED,
        }

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
        return not self.effective_facts.profile_updates.is_empty

    def _original_fact_elements(self) -> dict[str, list[FactElement]]:
        """薬歴IDと原本位置から安定した配列要素IDを導出する。"""
        result: dict[str, list[FactElement]] = {}
        for field_name in FACT_ARRAY_TYPES:
            if field_name.startswith("profile_updates."):
                values = getattr(self.profile_updates, field_name.split(".", 1)[1])
            else:
                values = getattr(self, field_name)
            result[field_name] = [
                FactElement(
                    id=str(uuid5(self.id.value, f"{field_name}:{index}")),
                    value=value,
                )
                for index, value in enumerate(values)
            ]
        return result

    def _replay_facts(
        self,
    ) -> tuple[EffectiveMedicationHistoryFacts, dict[str, list[FactElement]]]:
        """訂正の追記順に有効値と要素IDを再生する。"""
        facts = EffectiveMedicationHistoryFacts(
            counselor_id=self.counselor_id,
            counseled_at=self.counseled_at,
            method=self.method,
            handbook_status=self.handbook_status,
            residual_drug=self.residual_drug,
            information_sheet_provided=self.information_sheet_provided,
            profile_updates=self.profile_updates,
            additional_notes=self.additional_notes,
            billing_additions=self.billing_additions,
            source_system=self.source_system,
            delay_reason=self.delay_reason,
            review_result=self.review_result,
        )
        elements = self._original_fact_elements()
        for correction in self.fact_corrections:
            field_name = correction.field_name
            if field_name in FACT_ARRAY_TYPES:
                items = elements[field_name]
                if correction.operation == "append":
                    if correction.element_id is None or correction.after is None:
                        raise MedicationHistoryDomainError(
                            "追加要素のIDと値が必要です。"
                        )
                    items.append(
                        FactElement(id=correction.element_id, value=correction.after)
                    )
                else:
                    position = next(
                        (
                            index
                            for index, item in enumerate(items)
                            if item.id == correction.target
                        ),
                        None,
                    )
                    if position is None:
                        raise MedicationHistoryDomainError(
                            "訂正対象の要素がありません。"
                        )
                    if correction.operation == "retract":
                        items.pop(position)
                    elif correction.after is not None:
                        items[position] = FactElement(
                            id=correction.target, value=correction.after
                        )
            elif field_name.startswith("profile_updates."):
                facts = replace(
                    facts,
                    profile_updates=_replace_fact_field(
                        facts.profile_updates,
                        field_name.split(".", 1)[1],
                        correction.after,
                    ),
                )
            else:
                facts = _replace_fact_field(facts, field_name, correction.after)
        profile_updates = facts.profile_updates
        for field_name, items in elements.items():
            values = tuple(item.value for item in items)
            if field_name.startswith("profile_updates."):
                profile_updates = _replace_fact_field(
                    profile_updates, field_name.split(".", 1)[1], values
                )
            else:
                facts = _replace_fact_field(facts, field_name, values)
        return replace(facts, profile_updates=profile_updates), elements

    @property
    def effective_facts(self) -> EffectiveMedicationHistoryFacts:
        """訂正後の有効な事実を返す。原本は保持する。"""
        return self._replay_facts()[0]

    def fact_elements(self, field_name: str) -> tuple[FactElement, ...]:
        """有効な配列要素を安定したIDとともに返す。"""
        if field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("指定した項目は配列ではありません。")
        return tuple(self._replay_facts()[1][field_name])

    def original_fact_elements(self, field_name: str) -> tuple[FactElement, ...]:
        """原本配列の要素と不変のIDを返す。"""
        if field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("指定した項目は配列ではありません。")
        return tuple(self._original_fact_elements()[field_name])

    def _ensure_fact_corrections_are_valid(self) -> None:
        """訂正IDの重複と下書きへの訂正を拒否する。"""
        if self.fact_corrections and not self.is_projection_eligible:
            raise MedicationHistoryNotFinalizedError()
        ids = [item.id for item in self.fact_corrections]
        if len(ids) != len(set(ids)):
            raise MedicationHistoryDomainError("薬歴訂正IDが重複しています。")
        if self.status is MedicationHistoryStatus.FINALIZED and any(
            item.field_name == "review_result" and item.after is None
            for item in self.fact_corrections
        ):
            raise MedicationHistoryDomainError("レビュー結果は訂正で解除できません。")
        self._replay_facts()

    def correct_fact(
        self,
        *,
        target: str,
        operation: str = "replace",
        reason: str,
        corrected_by: StaffId,
        recorded_at: datetime,
        value: object = _FACT_VALUE_ABSENT,
    ) -> Self:
        """確定・移行済み薬歴の事実訂正を監査値付きで追記する。"""
        if not self.is_projection_eligible:
            raise MedicationHistoryNotFinalizedError()
        if not reason.strip():
            raise MedicationHistoryDomainError("訂正理由を入力してください。")
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise MedicationHistoryDomainError("訂正日時にはタイムゾーンが必要です。")
        if operation not in {"replace", "retract", "append"}:
            raise MedicationHistoryDomainError("訂正操作が正しくありません。")
        facts, elements = self._replay_facts()
        field_name = target
        if target not in FACT_FIELD_TYPES and target not in FACT_ARRAY_TYPES:
            field_name = next(
                (
                    name
                    for name, items in elements.items()
                    if any(item.id == target for item in items)
                ),
                "",
            )
        if field_name not in FACT_FIELD_TYPES and field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("訂正対象がありません。")
        is_array = field_name in FACT_ARRAY_TYPES
        if operation == "append" and (not is_array or target != field_name):
            raise MedicationHistoryDomainError("配列への追加対象が正しくありません。")
        if operation != "append" and is_array and target == field_name:
            raise MedicationHistoryDomainError("配列要素のIDを指定してください。")
        if operation == "retract":
            if value is not _FACT_VALUE_ABSENT:
                raise MedicationHistoryDomainError("取消しに新しい値は指定できません。")
            after: object | None = None
        else:
            if value is _FACT_VALUE_ABSENT:
                raise MedicationHistoryDomainError("訂正後の値を指定してください。")
            expected = (FACT_ARRAY_TYPES if is_array else FACT_FIELD_TYPES)[field_name]
            if value is not None and (
                type(value) is not bool
                if expected is bool
                else not isinstance(value, expected)
            ):
                raise MedicationHistoryDomainError("訂正値の型が対象項目と異なります。")
            if is_array and value is None:
                raise MedicationHistoryDomainError("配列に空の要素は追加できません。")
            after = value
        if is_array:
            before = next(
                (item.value for item in elements[field_name] if item.id == target),
                None,
            )
            if operation != "append" and before is None:
                raise MedicationHistoryDomainError("訂正対象の要素がありません。")
        elif field_name.startswith("profile_updates."):
            before = getattr(facts.profile_updates, field_name.split(".", 1)[1])
        else:
            before = getattr(facts, field_name)
        if operation == "retract" and not is_array and before is None:
            raise MedicationHistoryDomainError("取消し対象の値がありません。")
        event = MedicationHistoryFactCorrection(
            id=str(uuid7()),
            target=target,
            field_name=field_name,
            operation=operation,
            before=before,
            after=after,
            reason=reason.strip(),
            corrected_by=corrected_by,
            recorded_at=FactCorrectionTimestamp(recorded_at),
            element_id=str(uuid7()) if operation == "append" else None,
        )
        return replace(self, fact_corrections=(*self.fact_corrections, event))

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        *,
        event_id: EventId,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        dispensing_id: DispensingId | None,
        prescription_id: PrescriptionId | None,
        counselor_id: StaffId | None,
        counseled_at: CounselingTimestamp | None,
        method: CounselingMethod | None,
        soap: SoapRecord,
        handbook_status: HandbookStatus | None,
        residual_drug: ResidualDrugRecord | None,
        information_sheet_provided: bool | None = None,
        profile_updates: ProfileUpdateIntents | None = None,
        additional_notes: tuple[CategorizedNote, ...] = (),
        billing_additions: tuple[BillingAddition, ...] = (),
        source_system: MedicationHistorySourceSystem | None = None,
        imported_at: MedicationHistoryImportTimestamp | None = None,
        recorded_by: StaffId | None = None,
        recorded_at: MedicationHistoryRecordedTimestamp | None = None,
    ) -> Self:
        """服薬指導の記録を下書きとして起こす。"""
        return cls(
            id=MedicationHistoryRecordId.generate(),
            event_id=event_id,
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
            billing_additions=billing_additions,
            source_system=source_system,
            imported_at=imported_at,
            recorded_by=recorded_by,
            recorded_at=recorded_at,
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
        billing_additions: tuple[BillingAddition, ...] | None = None,
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
            billing_additions=billing_additions
            if billing_additions is not None
            else self.billing_additions,
        )

    def finalize(
        self,
        *,
        counselor_id: StaffId | None = None,
        counseled_at: CounselingTimestamp | None = None,
        finalized_at: FinalizedTimestamp | None = None,
        finalized_by: StaffId | None = None,
        delay_reason: FinalizationDelayReason | None = None,
        review_result: MedicationHistoryReviewResult | None = None,
    ) -> Self:
        """薬歴を確定する。

        確定日時と確定者は呼び出し元から明示する。指導日時・指導者から監査値を
        推定しない。指導実績のない取込下書きは、実際の指導者と指導日時も必要。
        """
        self._ensure_not_finalized()
        if finalized_at is None or finalized_by is None:
            raise FinalizationStaffRequiredError()
        if review_result is None:
            raise MedicationHistoryDomainError(
                "薬歴確定時のレビュー結果を指定してください。"
            )
        supplied_counselor = counselor_id is not None
        supplied_counseled_at = counseled_at is not None
        if supplied_counselor != supplied_counseled_at:
            raise MedicationHistoryDomainError(
                "指導者と指導日時は両方指定してください。"
            )
        actual_counselor_id: StaffId | None = self.counselor_id
        actual_counseled_at: CounselingTimestamp | None = self.counseled_at
        if supplied_counselor:
            if counselor_id is None or counseled_at is None:
                raise MedicationHistoryDomainError(
                    "指導者と指導日時は両方指定してください。"
                )
            if (
                self.counselor_id is not None and self.counselor_id != counselor_id
            ) or (self.counseled_at is not None and self.counseled_at != counseled_at):
                raise MedicationHistoryDomainError(
                    "記録済みの指導者または指導日時は確定時に変更できません。"
                )
            actual_counselor_id = counselor_id
            actual_counseled_at = counseled_at
        if actual_counselor_id is None or actual_counseled_at is None:
            raise MedicationHistoryDomainError(
                "薬歴を確定するには実際の指導者と指導日時が必要です。"
            )
        with_counseling = replace(
            self,
            counselor_id=actual_counselor_id,
            counseled_at=actual_counseled_at,
        )
        return replace(
            with_counseling,
            status=MedicationHistoryStatus.FINALIZED,
            finalized_at=finalized_at,
            finalized_by=finalized_by,
            delay_reason=delay_reason,
            review_result=review_result,
        )

    def amend(
        self,
        *,
        amended_soap: SoapRecord,
        reason: AmendmentReason,
        amended_by: StaffId,
        amended_at: AmendmentTimestamp,
        amendment_id: str | None = None,
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
        effective_amendment_id = amendment_id or str(uuid7())
        amendment = MedicationHistoryAmendment(
            amended_soap=amended_soap,
            reason=reason,
            amended_by=amended_by,
            amended_at=amended_at,
            amendment_id=effective_amendment_id,
        )
        return replace(self, amendments=(*self.amendments, amendment))

    def _ensure_not_finalized(self) -> None:
        """確定済でないことを保証する。"""
        if self.status is not MedicationHistoryStatus.DRAFT:
            raise MedicationHistoryAlreadyFinalizedError()

    def add_tracing_report(self, report: TracingReport) -> Self:
        """確定済の薬歴に処方医へのトレーシングレポート提供記録を追加する。

        Raises:
            TracingReportOnDraftError: 薬歴が未確定（下書き）の場合。
            TracingReportDateBeforeCounselingError: 初回指導日時より前の提供日時の場合。
            DuplicatedTracingReportIdError: 同一のレポートIDが既に存在する場合。
        """
        if not self.is_finalized:
            raise TracingReportOnDraftError()
        if self.counseled_at is None:
            raise MedicationHistoryDomainError("確定済の薬歴に指導日時がありません。")
        if report.provided_at.value < self.counseled_at.value:
            raise TracingReportDateBeforeCounselingError()
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
        """保留または調査中の外部処方訂正が存在するか。"""
        return any(
            correction.status is not ExternalCorrectionStatus.RESOLVED
            and not correction.is_acknowledged
            for correction in self.external_corrections
        )

    def record_external_correction(
        self, correction: ExternalPrescriptionCorrection
    ) -> Self:
        """確定済みの記録を壊さず外部処方訂正を追記する。

        確定済み薬歴の原本（SOAP・確定日時・確定者）は真正性保護のため不可逆凍結し、
        外部から発生した処方変更・調剤訂正の事実を本証跡として記録する。
        """
        existing = next(
            (
                item
                for item in self.external_corrections
                if item.correction_id == correction.correction_id
            ),
            None,
        )
        if existing is not None:
            if (
                existing.kind == correction.kind
                and existing.source_document_number == correction.source_document_number
                and existing.reason == correction.reason
                and existing.details == correction.details
            ):
                return self
            raise MedicationHistoryDomainError(
                "同一の外部訂正IDに異なる訂正内容を登録できません。"
            )
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
            status=ExternalCorrectionStatus.RESOLVED,
        )
        updated_corrections = tuple(
            updated_correction if c.correction_id == correction_id else c
            for c in self.external_corrections
        )
        return replace(self, external_corrections=updated_corrections)

    def review_external_correction(
        self,
        *,
        correction_id: str,
        decision: ExternalCorrectionDecision,
        reason: str,
        reviewed_by: StaffId,
        reviewed_at: ExternalCorrectionTimestamp,
        amended_soap: SoapRecord | None = None,
        matched_prescription_id: PrescriptionId | None = None,
    ) -> Self:
        """外部訂正の判断を履歴へ追記し、最終判断だけを解決済みにする。"""
        if not self.is_finalized:
            raise MedicationHistoryNotFinalizedError()
        target = next(
            (
                item
                for item in self.external_corrections
                if item.correction_id == correction_id
            ),
            None,
        )
        if target is None:
            raise MedicationHistoryDomainError("指定された外部訂正IDが存在しません。")
        if target.status is ExternalCorrectionStatus.RESOLVED or target.is_acknowledged:
            raise MedicationHistoryDomainError("解決済みの外部訂正は再判断できません。")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise MedicationHistoryDomainError("外部訂正の判断理由は必須です。")

        amendment_id: str | None = None
        if decision is ExternalCorrectionDecision.AMEND:
            if amended_soap is None:
                raise MedicationHistoryDomainError("追記するSOAPを指定してください。")
            amendment_id = str(uuid7())
            updated = self.amend(
                amended_soap=amended_soap,
                reason=AmendmentReason(normalized_reason),
                amended_by=reviewed_by,
                amended_at=AmendmentTimestamp(reviewed_at.value),
                amendment_id=amendment_id,
            )
        else:
            updated = self
        if (
            decision is ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
            and matched_prescription_id is None
        ):
            raise MedicationHistoryDomainError("照合先の処方IDを指定してください。")
        if (
            decision is not ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
            and matched_prescription_id is not None
        ):
            raise MedicationHistoryDomainError(
                "照合先の処方IDは照合判断の場合だけ指定できます。"
            )

        is_final_decision = decision is not ExternalCorrectionDecision.INVESTIGATING
        event = ExternalCorrectionReviewEvent(
            decision=decision,
            reason=normalized_reason,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            amendment_id=amendment_id,
            matched_prescription_id=matched_prescription_id,
        )
        updated_target = replace(
            target,
            status=(
                ExternalCorrectionStatus.RESOLVED
                if is_final_decision
                else ExternalCorrectionStatus.INVESTIGATING
            ),
            review_events=(*target.review_events, event),
            acknowledged_by=reviewed_by
            if is_final_decision
            else target.acknowledged_by,
            acknowledged_at=reviewed_at
            if is_final_decision
            else target.acknowledged_at,
        )
        updated_corrections = tuple(
            updated_target if item.correction_id == correction_id else item
            for item in updated.external_corrections
        )
        return replace(updated, external_corrections=updated_corrections)

    def calculate_and_set_retention_expiry(
        self, catalog: PreservationPolicyCatalog
    ) -> Self:
        """保存期間ポリシーに基づいて法定保存満了日を設定する。"""
        if self.counseled_at is None:
            raise MedicationHistoryDomainError(
                "保存期間の起算には実際の指導日時が必要です。"
            )
        base_date = self.counseled_at.value.date()
        expiry_date = catalog.calculate_expiry_date(base_date)
        return replace(self, retention_expiry_date=expiry_date)
