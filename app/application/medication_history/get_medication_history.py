"""薬歴をApplication DTOへ変換して取得する処理。"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import cast
from uuid import UUID

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.common.optional_conversion import unwrap
from app.application.medication_history.reference import (
    MedicationHistoryEventBoundary,
    MedicationHistoryEventReference,
)
from app.application.medication_history.support import load_record_or_raise
from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.medication_history.fact_correction import FACT_ARRAY_TYPES, FactElement
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    HandbookStatus,
    LabeledNote,
    MedicationHistoryAmendment,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
    TracingReport,
    TracingReportResponse,
)
from app.domain.patient.primitives import PatientId


def _fact_json(value: object) -> object:
    """薬歴の監査事実をAPIで読める構造へ変換する。"""
    if isinstance(value, DomainPrimitive):
        return _fact_json(value.value)
    if isinstance(value, Enum):
        return _fact_json(value.value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _fact_json(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, tuple | list):
        return [_fact_json(item) for item in value]
    return value


def _element_json(element: FactElement) -> dict[str, object]:
    """配列要素IDと値の項目を1つの表示単位にする。"""
    payload = _fact_json(element.value)
    if isinstance(payload, dict):
        return {"id": element.id, **payload}
    return {"id": element.id, "value": payload}


def _profile_updates_json(
    record: MedicationHistoryRecord, *, original: bool
) -> dict[str, object]:
    """原本または有効な頭書き差分を要素IDつきで返す。"""
    updates = (
        record.profile_updates if original else record.effective_facts.profile_updates
    )
    result: dict[str, object] = {}
    for item in fields(ProfileUpdateIntents):
        field_name = f"profile_updates.{item.name}"
        if field_name in FACT_ARRAY_TYPES:
            elements = (
                record.original_fact_elements(field_name)
                if original
                else record.fact_elements(field_name)
            )
            result[item.name] = [_element_json(element) for element in elements]
        else:
            result[item.name] = _fact_json(getattr(updates, item.name))
    return result


def _original_facts_json(record: MedicationHistoryRecord) -> dict[str, object]:
    """交付時の記録値を訂正後の表示と独立して返す。"""
    return {
        "counselor_id": _fact_json(record.counselor_id),
        "counseled_at": _fact_json(record.counseled_at),
        "method": _fact_json(record.method),
        "handbook_status": _fact_json(record.handbook_status),
        "residual_drug": _fact_json(record.residual_drug),
        "information_sheet_provided": record.information_sheet_provided,
        "profile_updates": _profile_updates_json(record, original=True),
        "additional_notes": [
            _element_json(item)
            for item in record.original_fact_elements("additional_notes")
        ],
        "billing_additions": [
            _element_json(item)
            for item in record.original_fact_elements("billing_additions")
        ],
        "source_system": _fact_json(record.source_system),
        "delay_reason": _fact_json(record.delay_reason),
        "review_result": _fact_json(record.review_result),
    }


def _fact_corrections_json(
    record: MedicationHistoryRecord,
) -> tuple[dict[str, object], ...]:
    """追記順を保った監査履歴を返す。"""
    return tuple(
        {
            "id": item.id,
            "target": item.target,
            "field_name": item.field_name,
            "operation": item.operation,
            "before": _fact_json(item.before),
            "after": _fact_json(item.after),
            "reason": item.reason,
            "corrected_by": _fact_json(item.corrected_by),
            "recorded_at": _fact_json(item.recorded_at),
            "element_id": item.element_id,
        }
        for item in record.fact_corrections
    )


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

    @classmethod
    def from_value(cls, value: MedicationHistoryAmendment) -> AmendmentDto:
        """追記からDTOを生成する。"""
        return cls(
            amended_soap=SoapDto.from_value(value.amended_soap),
            reason=value.reason.value,
            amended_by=str(value.amended_by.value),
            amended_at=value.amended_at.value.isoformat(),
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
            response=(
                TracingReportResponseDto.from_value(value.response)
                if value.response is not None
                else None
            ),
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
            points=value.points,
            quantity=value.quantity,
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
    #: 交付時に記録したSOAP。追記があっても書き換わらない。
    soap: SoapDto
    #: 追記を反映した現時点で有効なSOAP。
    effective_soap: SoapDto
    handbook_status: HandbookStatusDto | None
    residual_drug: ResidualDrugDto | None
    information_sheet_provided: bool | None
    source_system: str | None
    imported_at: str | None
    amendments: tuple[AmendmentDto, ...]
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
            event_type_id=(
                str(event.event_type_id.value) if event is not None else None
            ),
            event_type_name=(
                event.event_type_name.value if event is not None else None
            ),
            event_occurred_at=(
                event.occurred_at.value.isoformat()
                if event is not None and event.occurred_at is not None
                else None
            ),
            event_occurred_at_is_unknown=(
                event is not None and event.occurred_at is None
            ),
            dispensing_id=(
                str(record.dispensing_id.value)
                if record.dispensing_id is not None
                else None
            ),
            prescription_id=(
                str(record.prescription_id.value)
                if record.prescription_id is not None
                else None
            ),
            counselor_id=(
                str(facts.counselor_id.value)
                if facts.counselor_id is not None
                else None
            ),
            counseled_at=(
                facts.counseled_at.value.isoformat()
                if facts.counseled_at is not None
                else None
            ),
            method=unwrap(facts.method),
            status=record.status.value,
            soap=SoapDto.from_value(record.soap),
            effective_soap=SoapDto.from_value(record.effective_soap),
            handbook_status=(
                HandbookStatusDto.from_value(facts.handbook_status)
                if facts.handbook_status is not None
                else None
            ),
            residual_drug=(
                ResidualDrugDto.from_value(facts.residual_drug)
                if facts.residual_drug is not None
                else None
            ),
            information_sheet_provided=facts.information_sheet_provided,
            source_system=unwrap(facts.source_system),
            imported_at=(
                record.imported_at.value.isoformat()
                if record.imported_at is not None
                else None
            ),
            amendments=tuple(
                AmendmentDto.from_value(item) for item in record.amendments
            ),
            updates_profile=record.updates_profile,
            profile_updates=_profile_updates_json(record, original=False),
            original_facts=_original_facts_json(record),
            fact_corrections=_fact_corrections_json(record),
            additional_notes=tuple(
                CategorizedNoteDto.from_value(
                    cast(CategorizedNote, element.value), element_id=element.id
                )
                for element in record.fact_elements("additional_notes")
            ),
            billing_additions=tuple(
                BillingAdditionDto.from_value(
                    cast(BillingAddition, element.value), element_id=element.id
                )
                for element in record.fact_elements("billing_additions")
            ),
            tracing_reports=tuple(
                TracingReportDto.from_value(report) for report in record.tracing_reports
            ),
            finalized_at=(
                record.finalized_at.value.isoformat()
                if record.finalized_at is not None
                else None
            ),
            finalized_by=(
                str(record.finalized_by.value)
                if record.finalized_by is not None
                else None
            ),
            delay_reason=unwrap(facts.delay_reason),
            recorded_by=(
                str(record.recorded_by.value)
                if record.recorded_by is not None
                else None
            ),
            review_result=unwrap(facts.review_result),
            recorded_at=(
                record.recorded_at.value.isoformat()
                if record.recorded_at is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class GetMedicationHistoryQuery:
    """薬歴取得の入力データ。"""

    corporate_id: str
    record_id: str


class GetMedicationHistoryUseCase:
    """法人境界を確認して薬歴を取得する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        event_reference: MedicationHistoryEventBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._event_reference = event_reference

    async def execute(self, query: GetMedicationHistoryQuery) -> MedicationHistoryDto:
        """指定法人の薬歴をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        event = (
            await self._event_reference.get(
                corporate_id=corporate_id,
                event_id=record.event_id,
            )
            if self._event_reference is not None
            else None
        )
        return MedicationHistoryDto.from_entity(record, event=event)


@dataclass(frozen=True, kw_only=True)
class FollowUpSourceDto:
    """店舗横断フォローアップ作成に必要な元Eventの参照情報。"""

    event_id: EventId
    patient_id: PatientId


@dataclass(frozen=True, kw_only=True)
class GetFollowUpSourceQuery:
    """確定済み薬歴をフォローアップの関連元として解決する入力。"""

    corporate_id: str
    record_id: str


class GetFollowUpSourceUseCase:
    """確定済み薬歴から本文を読まず関連Eventだけを取り出す。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetFollowUpSourceQuery) -> FollowUpSourceDto:
        """確定済み元薬歴のEvent参照を返し、他店舗本文は取得しない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        source = await self._repository.get_finalized_source_for_follow_up(
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        if source is None:
            raise NotFoundError(
                "指定された確定済み薬歴が見つかりません。",
                code="MEDICATION_HISTORY_NOT_FOUND",
            )
        return FollowUpSourceDto(event_id=source.event_id, patient_id=source.patient_id)


@dataclass(frozen=True, kw_only=True)
class ListMedicationHistoriesQuery:
    """患者の薬歴タイムライン取得の入力データ。"""

    corporate_id: str
    patient_id: str


class ListMedicationHistoriesByPatientUseCase:
    """患者の薬歴を服薬指導日時の昇順で返す。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        event_reference: MedicationHistoryEventBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._event_reference = event_reference

    async def execute(
        self, query: ListMedicationHistoriesQuery
    ) -> tuple[MedicationHistoryDto, ...]:
        """指定法人・患者の薬歴をDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        records = await self._repository.list_by_patient(
            corporate_id=corporate_id,
            patient_id=PatientId.parse(query.patient_id),
        )
        result: list[MedicationHistoryDto] = []
        for record in records:
            event = (
                await self._event_reference.get(
                    corporate_id=corporate_id,
                    event_id=record.event_id,
                )
                if self._event_reference is not None
                else None
            )
            result.append(MedicationHistoryDto.from_entity(record, event=event))
        return tuple(result)
