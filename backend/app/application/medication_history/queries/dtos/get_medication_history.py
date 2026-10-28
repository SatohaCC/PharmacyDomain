"""Applicationのget_medication_historyを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from app.application.common.optional_conversion import unwrap
from app.application.medication_history.queries.dtos.fact_values import (
    _fact_corrections_json,
    _original_facts_json,
    _profile_updates_json,
)
from app.application.medication_history.values import MedicationHistoryEventReference
from app.domain.care_event.identifiers import EventId
from app.domain.medication_history.entities import (
    MedicationHistoryRecord,
    TracingReport,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    ExternalCorrectionReviewEvent,
    ExternalPrescriptionCorrection,
    HandbookStatus,
    LabeledNote,
    MedicationHistoryAmendment,
    ResidualDrugRecord,
    SoapRecord,
    TracingReportResponse,
)
from app.domain.patient.identifiers import PatientId


@dataclass(frozen=True, kw_only=True)
class LabeledNoteDto:
    """ラベル付き記述1件の出力DTO。"""

    category: str
    category_label: str
    text: str

    @classmethod
    def from_value(cls, value: LabeledNote) -> LabeledNoteDto:
        """ラベル付き記述からDTOを生成する。"""
        return cls(
            category=value.category.value,
            category_label=value.category.label,
            text=value.text.value,
        )


@dataclass(frozen=True, kw_only=True)
class SoapDto:
    """SOAPの出力DTO。"""

    subjective: tuple[LabeledNoteDto, ...]
    objective: tuple[LabeledNoteDto, ...]
    assessment: tuple[LabeledNoteDto, ...]
    plan: tuple[LabeledNoteDto, ...]

    @classmethod
    def from_value(cls, value: SoapRecord) -> SoapDto:
        """SOAPからDTOを生成する。"""
        return cls(
            subjective=tuple(
                LabeledNoteDto.from_value(item) for item in value.subjective
            ),
            objective=tuple(
                LabeledNoteDto.from_value(item) for item in value.objective
            ),
            assessment=tuple(
                LabeledNoteDto.from_value(item) for item in value.assessment
            ),
            plan=tuple(LabeledNoteDto.from_value(item) for item in value.plan),
        )


@dataclass(frozen=True, kw_only=True)
class ResidualDrugDto:
    """残薬状況の出力DTO。"""

    has_residual_drugs: bool
    quantity: int | None
    reason: str | None

    @classmethod
    def from_value(cls, value: ResidualDrugRecord) -> ResidualDrugDto:
        """残薬状況からDTOを生成する。"""
        return cls(
            has_residual_drugs=value.has_residual_drugs,
            quantity=unwrap(value.quantity),
            reason=unwrap(value.reason),
        )


@dataclass(frozen=True, kw_only=True)
class HandbookStatusDto:
    """お薬手帳の活用状況の出力DTO。"""

    presented: bool
    not_presented_reason: str | None
    guidance_provided: bool | None
    multiple_handbooks_not_consolidated_reason: str | None

    @classmethod
    def from_value(cls, value: HandbookStatus) -> HandbookStatusDto:
        """活用状況からDTOを生成する。"""
        consolidation = value.multiple_handbooks_not_consolidated_reason
        return cls(
            presented=value.presented,
            not_presented_reason=unwrap(value.not_presented_reason),
            guidance_provided=value.guidance_provided,
            multiple_handbooks_not_consolidated_reason=unwrap(consolidation),
        )


@dataclass(frozen=True, kw_only=True)
class AmendmentDto:
    """確定済薬歴への追記の出力DTO。"""

    amended_soap: SoapDto
    reason: str
    amended_by: str
    amended_at: str
    amendment_id: str | None = None

    @classmethod
    def from_value(cls, value: MedicationHistoryAmendment) -> AmendmentDto:
        """追記からDTOを生成する。"""
        return cls(
            amended_soap=SoapDto.from_value(value.amended_soap),
            reason=value.reason.value,
            amended_by=str(value.amended_by.value),
            amended_at=value.amended_at.value.isoformat(),
            amendment_id=unwrap(value.amendment_id),
        )


@dataclass(frozen=True, kw_only=True)
class ExternalCorrectionReviewEventDto:
    """外部訂正への判断イベントDTO。"""

    decision: str
    reason: str
    reviewed_by: str
    reviewed_at: str
    matched_prescription_id: str | None
    amendment_id: str | None = None

    @classmethod
    def from_value(
        cls, value: ExternalCorrectionReviewEvent
    ) -> ExternalCorrectionReviewEventDto:
        """レビューイベントから監査表示用DTOを生成する。"""
        event = value
        return cls(
            decision=event.decision.value,
            reason=event.reason.value,
            reviewed_by=str(event.reviewed_by.value),
            reviewed_at=event.reviewed_at.value.isoformat(),
            amendment_id=unwrap(event.amendment_id),
            matched_prescription_id=str(event.matched_prescription_id.value)
            if event.matched_prescription_id is not None
            else None,
        )


@dataclass(frozen=True, kw_only=True)
class ExternalPrescriptionCorrectionDto:
    """外部処方訂正の受信事実と判断履歴DTO。"""

    correction_id: str
    kind: str
    status: str
    corrected_at: str
    source_document_number: str
    reason: str
    details: str | None
    acknowledged_by: str | None
    acknowledged_at: str | None
    review_events: tuple[ExternalCorrectionReviewEventDto, ...]

    @classmethod
    def from_value(
        cls, value: ExternalPrescriptionCorrection
    ) -> ExternalPrescriptionCorrectionDto:
        """訂正証跡から旧確認表現も含むDTOを生成する。"""
        return cls(
            correction_id=value.correction_id.value,
            kind=value.kind.value,
            status="resolved" if value.is_acknowledged else value.status.value,
            corrected_at=value.corrected_at.value.isoformat(),
            source_document_number=value.source_document_number.value,
            reason=value.reason.value,
            details=unwrap(value.details),
            acknowledged_by=str(value.acknowledged_by.value)
            if value.acknowledged_by is not None
            else None,
            acknowledged_at=value.acknowledged_at.value.isoformat()
            if value.acknowledged_at is not None
            else None,
            review_events=tuple(
                ExternalCorrectionReviewEventDto.from_value(event)
                for event in value.review_events
            ),
        )


@dataclass(frozen=True, kw_only=True)
class CategorizedNoteDto:
    """大区分・中区分に紐づく記載メモ1件の出力DTO。"""

    major_category_code: str
    medium_category_code: str
    text: str
    category: str
    id: str | None = None

    @classmethod
    def from_value(
        cls, value: CategorizedNote, *, element_id: str | None = None
    ) -> CategorizedNoteDto:
        """記載メモからDTOを生成する。"""
        return cls(
            major_category_code=value.major_category_code.value,
            medium_category_code=value.medium_category_code.value,
            text=value.text.value,
            category=value.statutory_category.value,
            id=element_id,
        )


@dataclass(frozen=True, kw_only=True)
class TracingReportResponseDto:
    """トレーシングレポートに対する処方医返答の出力DTO。"""

    responded_at: str
    action_type: str
    content: str
    received_by: str
    acknowledged_physician_name: str | None = None

    @classmethod
    def from_value(cls, value: TracingReportResponse) -> TracingReportResponseDto:
        """処方医返答値オブジェクトからDTOを生成する。"""
        return cls(
            responded_at=value.responded_at.value.isoformat(),
            action_type=value.action_type.value,
            content=value.content.value,
            received_by=str(value.received_by.value),
            acknowledged_physician_name=unwrap(value.acknowledged_physician_name),
        )


@dataclass(frozen=True, kw_only=True)
class TracingReportDto:
    """処方医への服薬情報等提供（トレーシングレポート）出力DTO。"""

    id: str
    reporter_id: str
    provided_at: str
    medical_institution_name: str
    physician_name: str
    category: str
    fee_category: str
    delivery_method: str
    content: str
    response: TracingReportResponseDto | None = None

    @classmethod
    def from_value(cls, value: TracingReport) -> TracingReportDto:
        """トレーシングレポート値オブジェクトからDTOを生成する。"""
        return cls(
            id=str(value.id.value),
            reporter_id=str(value.reporter_id.value),
            provided_at=value.provided_at.value.isoformat(),
            medical_institution_name=value.medical_institution_name.value,
            physician_name=value.physician_name.value,
            category=value.category.value,
            fee_category=value.fee_category.value,
            delivery_method=value.delivery_method.value,
            content=value.content.value,
            response=TracingReportResponseDto.from_value(value.response)
            if value.response is not None
            else None,
        )


@dataclass(frozen=True, kw_only=True)
class BillingAdditionDto:
    """算定加算1件の出力DTO。"""

    code: str
    name: str
    points: int | None
    quantity: int | None
    id: str | None = None

    @classmethod
    def from_value(
        cls, value: BillingAddition, *, element_id: str | None = None
    ) -> BillingAdditionDto:
        """算定加算からDTOを生成する。"""
        return cls(
            code=value.code.value,
            name=value.name.value,
            points=unwrap(value.points),
            quantity=unwrap(value.quantity),
            id=element_id,
        )


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryDto:
    """薬歴取得ユースケースの出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    event_id: str
    event_type_id: str | None
    event_type_name: str | None
    event_occurred_at: str | None
    event_occurred_at_is_unknown: bool
    dispensing_id: str | None
    prescription_id: str | None
    counselor_id: str | None
    counseled_at: str | None
    method: str | None
    status: str
    soap: SoapDto
    effective_soap: SoapDto
    handbook_status: HandbookStatusDto | None
    residual_drug: ResidualDrugDto | None
    information_sheet_provided: bool | None
    source_system: str | None
    imported_at: str | None
    amendments: tuple[AmendmentDto, ...]
    external_corrections: tuple[ExternalPrescriptionCorrectionDto, ...]
    updates_profile: bool
    profile_updates: dict[str, object]
    original_facts: dict[str, object]
    fact_corrections: tuple[dict[str, object], ...]
    additional_notes: tuple[CategorizedNoteDto, ...] = ()
    billing_additions: tuple[BillingAdditionDto, ...] = ()
    tracing_reports: tuple[TracingReportDto, ...] = ()
    finalized_at: str | None = None
    finalized_by: str | None = None
    delay_reason: str | None = None
    recorded_by: str | None = None
    review_result: str | None = None
    recorded_at: str | None = None

    @classmethod
    def from_entity(
        cls,
        record: MedicationHistoryRecord,
        *,
        event: MedicationHistoryEventReference | None = None,
    ) -> MedicationHistoryDto:
        """薬歴集約からDTOを生成する。"""
        facts = record.effective_facts
        return cls(
            id=str(record.id.value),
            corporate_id=str(record.corporate_id.value),
            store_id=str(record.store_id.value),
            patient_id=str(record.patient_id.value),
            event_id=str(record.event_id.value),
            event_type_id=str(event.event_type_id.value) if event is not None else None,
            event_type_name=event.event_type_name.value if event is not None else None,
            event_occurred_at=event.occurred_at.value.isoformat()
            if event is not None and event.occurred_at is not None
            else None,
            event_occurred_at_is_unknown=event is not None
            and event.occurred_at is None,
            dispensing_id=str(record.dispensing_id.value)
            if record.dispensing_id is not None
            else None,
            prescription_id=str(record.prescription_id.value)
            if record.prescription_id is not None
            else None,
            counselor_id=str(facts.counselor_id.value)
            if facts.counselor_id is not None
            else None,
            counseled_at=facts.counseled_at.value.isoformat()
            if facts.counseled_at is not None
            else None,
            method=unwrap(facts.method),
            status=record.status.value,
            soap=SoapDto.from_value(record.soap),
            effective_soap=SoapDto.from_value(record.effective_soap),
            handbook_status=HandbookStatusDto.from_value(facts.handbook_status)
            if facts.handbook_status is not None
            else None,
            residual_drug=ResidualDrugDto.from_value(facts.residual_drug)
            if facts.residual_drug is not None
            else None,
            information_sheet_provided=facts.information_sheet_provided,
            source_system=unwrap(facts.source_system),
            imported_at=record.imported_at.value.isoformat()
            if record.imported_at is not None
            else None,
            amendments=tuple(
                AmendmentDto.from_value(item) for item in record.amendments
            ),
            external_corrections=tuple(
                ExternalPrescriptionCorrectionDto.from_value(item)
                for item in record.external_corrections
            ),
            updates_profile=record.updates_profile,
            profile_updates=_profile_updates_json(record, original=False),
            original_facts=_original_facts_json(record),
            fact_corrections=_fact_corrections_json(record),
            additional_notes=tuple(
                CategorizedNoteDto.from_value(
                    cast(CategorizedNote, element.value), element_id=element.id.value
                )
                for element in record.fact_elements("additional_notes")
            ),
            billing_additions=tuple(
                BillingAdditionDto.from_value(
                    cast(BillingAddition, element.value), element_id=element.id.value
                )
                for element in record.fact_elements("billing_additions")
            ),
            tracing_reports=tuple(
                TracingReportDto.from_value(report) for report in record.tracing_reports
            ),
            finalized_at=record.finalized_at.value.isoformat()
            if record.finalized_at is not None
            else None,
            finalized_by=str(record.finalized_by.value)
            if record.finalized_by is not None
            else None,
            delay_reason=unwrap(facts.delay_reason),
            recorded_by=str(record.recorded_by.value)
            if record.recorded_by is not None
            else None,
            review_result=unwrap(facts.review_result),
            recorded_at=record.recorded_at.value.isoformat()
            if record.recorded_at is not None
            else None,
        )


@dataclass(frozen=True, kw_only=True)
class FollowUpSourceDto:
    """店舗横断フォローアップ作成に必要な元Eventの参照情報。"""

    event_id: EventId
    patient_id: PatientId
