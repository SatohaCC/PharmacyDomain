"""薬歴をApplication DTOへ変換して取得する処理。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    HandbookStatus,
    LabeledNote,
    MedicationHistoryAmendment,
    MedicationHistoryRecord,
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
    ResidualDrugRecord,
    SoapRecord,
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
            quantity=value.quantity.value if value.quantity is not None else None,
            reason=value.reason.value if value.reason is not None else None,
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
            not_presented_reason=(
                value.not_presented_reason.value
                if value.not_presented_reason is not None
                else None
            ),
            guidance_provided=value.guidance_provided,
            multiple_handbooks_not_consolidated_reason=(
                consolidation.value if consolidation is not None else None
            ),
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
class MedicationHistoryDto:
    """薬歴の出力DTO。"""

    id: str
    corporate_id: str
    store_id: str
    patient_id: str
    dispensing_id: str
    prescription_id: str
    counselor_id: str
    counseled_at: str
    method: str
    status: str
    #: 交付時に記録したSOAP。追記があっても書き換わらない。
    soap: SoapDto
    #: 追記を反映した現時点で有効なSOAP。
    effective_soap: SoapDto
    handbook_status: HandbookStatusDto
    residual_drug: ResidualDrugDto
    information_sheet_provided: bool
    amendments: tuple[AmendmentDto, ...]
    updates_profile: bool

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
            counselor_id=str(record.counselor_id.value),
            counseled_at=record.counseled_at.value.isoformat(),
            method=record.method.value,
            status=record.status.value,
            soap=SoapDto.from_value(record.soap),
            effective_soap=SoapDto.from_value(record.effective_soap),
            handbook_status=HandbookStatusDto.from_value(record.handbook_status),
            residual_drug=ResidualDrugDto.from_value(record.residual_drug),
            information_sheet_provided=record.information_sheet_provided,
            amendments=tuple(
                AmendmentDto.from_value(item) for item in record.amendments
            ),
            updates_profile=record.updates_profile,
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
