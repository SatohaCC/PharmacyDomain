"""薬歴をApplication DTOへ変換して取得する処理。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import unwrap
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
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
    FollowUpRecord,
    HandbookStatus,
    LabeledNote,
    MedicationHistoryAmendment,
    ResidualDrugRecord,
    SoapRecord,
    TracingReport,
    TracingReportResponse,
)
from app.domain.patient.primitives import PatientId


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

    @classmethod
    def from_value(cls, value: CategorizedNote) -> CategorizedNoteDto:
        """記載メモからDTOを生成する。"""
        return cls(
            major_category_code=value.major_category_code.value,
            medium_category_code=value.medium_category_code.value,
            text=value.text.value,
            category=value.statutory_category.value,
        )


@dataclass(frozen=True, kw_only=True)
class FollowUpDto:
    """服薬期間中のフォローアップ出力DTO。"""

    id: str
    counselor_id: str
    followed_up_at: str
    method: str | None
    soap: SoapDto
    handbook_status: HandbookStatusDto | None
    residual_drug: ResidualDrugDto | None
    information_sheet_provided: bool | None
    source_system: str | None
    additional_notes: tuple[CategorizedNoteDto, ...] = ()
    updates_profile: bool = False

    @classmethod
    def from_value(cls, value: FollowUpRecord) -> FollowUpDto:
        """フォローアップ値オブジェクトからDTOを生成する。"""
        return cls(
            id=str(value.id.value),
            counselor_id=str(value.counselor_id.value),
            followed_up_at=value.followed_up_at.value.isoformat(),
            method=unwrap(value.method),
            soap=SoapDto.from_value(value.soap),
            handbook_status=(
                HandbookStatusDto.from_value(value.handbook_status)
                if value.handbook_status is not None
                else None
            ),
            residual_drug=(
                ResidualDrugDto.from_value(value.residual_drug)
                if value.residual_drug is not None
                else None
            ),
            information_sheet_provided=value.information_sheet_provided,
            source_system=unwrap(value.source_system),
            additional_notes=tuple(
                CategorizedNoteDto.from_value(note) for note in value.additional_notes
            ),
            updates_profile=not value.profile_updates.is_empty,
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
    follow_up_id: str | None = None
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
            follow_up_id=(
                str(value.follow_up_id.value)
                if value.follow_up_id is not None
                else None
            ),
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

    @classmethod
    def from_value(cls, value: BillingAddition) -> BillingAdditionDto:
        """算定加算からDTOを生成する。"""
        return cls(
            code=value.code.value,
            name=value.name.value,
            points=value.points,
            quantity=value.quantity,
        )


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryDto:
    """薬歴取得ユースケースの出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    dispensing_id: str
    prescription_id: str
    record_kind: str
    source_record_id: str | None
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
    additional_notes: tuple[CategorizedNoteDto, ...] = ()
    billing_additions: tuple[BillingAdditionDto, ...] = ()
    follow_ups: tuple[FollowUpDto, ...] = ()
    tracing_reports: tuple[TracingReportDto, ...] = ()
    finalized_at: str | None = None
    finalized_by: str | None = None
    delay_reason: str | None = None
    recorded_by: str | None = None
    review_result: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None

    @classmethod
    def from_entity(cls, record: MedicationHistoryRecord) -> MedicationHistoryDto:
        """薬歴集約からDTOを生成する。"""
        return cls(
            id=str(record.id.value),
            corporate_id=str(record.corporate_id.value),
            store_id=str(record.store_id.value),
            patient_id=str(record.patient_id.value),
            dispensing_id=str(record.dispensing_id.value),
            prescription_id=str(record.prescription_id.value),
            record_kind=record.record_kind.value,
            source_record_id=(
                str(record.source_record_id.value)
                if record.source_record_id is not None
                else None
            ),
            counselor_id=(
                str(record.counselor_id.value)
                if record.counselor_id is not None
                else None
            ),
            counseled_at=(
                record.counseled_at.value.isoformat()
                if record.counseled_at is not None
                else None
            ),
            method=unwrap(record.method),
            status=record.status.value,
            soap=SoapDto.from_value(record.soap),
            effective_soap=SoapDto.from_value(record.effective_soap),
            handbook_status=(
                HandbookStatusDto.from_value(record.handbook_status)
                if record.handbook_status is not None
                else None
            ),
            residual_drug=(
                ResidualDrugDto.from_value(record.residual_drug)
                if record.residual_drug is not None
                else None
            ),
            information_sheet_provided=record.information_sheet_provided,
            source_system=unwrap(record.source_system),
            imported_at=(
                record.imported_at.value.isoformat()
                if record.imported_at is not None
                else None
            ),
            amendments=tuple(
                AmendmentDto.from_value(item) for item in record.amendments
            ),
            updates_profile=record.updates_profile,
            additional_notes=tuple(
                CategorizedNoteDto.from_value(note) for note in record.additional_notes
            ),
            billing_additions=tuple(
                BillingAdditionDto.from_value(ba) for ba in record.billing_additions
            ),
            follow_ups=tuple(FollowUpDto.from_value(fu) for fu in record.follow_ups),
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
            delay_reason=unwrap(record.delay_reason),
            recorded_by=(
                str(record.recorded_by.value)
                if record.recorded_by is not None
                else None
            ),
            review_result=unwrap(record.review_result),
            reviewed_by=(
                str(record.reviewed_by.value)
                if record.reviewed_by is not None
                else None
            ),
            reviewed_at=(
                record.reviewed_at.value.isoformat()
                if record.reviewed_at is not None
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
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

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
        return MedicationHistoryDto.from_entity(record)


@dataclass(frozen=True, kw_only=True)
class ListMedicationHistoriesQuery:
    """患者の薬歴タイムライン取得の入力データ。"""

    corporate_id: str
    patient_id: str


class ListMedicationHistoriesByPatientUseCase:
    """患者の薬歴を服薬指導日時の降順で返す。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

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
        return tuple(MedicationHistoryDto.from_entity(record) for record in records)
