"""MedicationHistoryユースケース間で共有する入力変換処理。

``to_optional_text`` は Shared Kernel の定義を**再エクスポートするだけ**にする。
複製するとコンテキストごとに正規化ルールが分岐する（AGENTS.md「空文字の正規化」）。
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from app.application.medication_history.exceptions import (
    MedicationHistoryNotFoundError,
)
from app.application.medication_history.inputs import (
    HandbookStatusInput,
    LabeledNoteInput,
    ProfileUpdateInput,
    ResidualDrugInput,
    SoapInput,
)
from app.base.application.support import to_optional_text
from app.base.domain.exceptions import DomainValidationError
from app.base.domain.medicine import MedicineName
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    AdverseReactionSymptom,
    AllergenName,
    AllergyReaction,
    AllergySeverity,
    ConcurrentCategory,
    ConditionName,
    ConditionStatus,
    CounselingNote,
    FamilyPharmacistIntent,
    GenericPreferenceIntent,
    GenericPreferenceType,
    HandbookConsolidationReason,
    HandbookNotPresentedReason,
    HandbookStatus,
    LabeledNote,
    LifestyleNote,
    LifestyleUpdateIntent,
    MedicationHistoryRecord,
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
    NewAdverseReactionIntent,
    NewAllergyIntent,
    NewConcurrentMedicationIntent,
    NewConditionIntent,
    ProfileUpdateIntents,
    ResidualDrugQuantity,
    ResidualDrugReason,
    ResidualDrugRecord,
    SoapRecord,
    StatutoryCategory,
    StopConcurrentMedicationIntent,
)
from app.domain.prescription.primitives import MedicalInstitutionName
from app.domain.staff.primitives import StaffId

__all__ = [
    "build_handbook_status",
    "build_profile_updates",
    "build_residual_drug",
    "build_soap",
    "load_record_or_raise",
    "parse_enum",
    "required_text",
    "to_optional_text",
]


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_enum[E: StrEnum](enum_type: type[E], raw: str, field_name: str) -> E:
    """入力文字列を指定の列挙へ変換する。"""
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name}が不正です。") from exc


def _build_notes(sources: tuple[LabeledNoteInput, ...]) -> tuple[LabeledNote, ...]:
    """ラベル付き記述の列を構成する。"""
    return tuple(
        LabeledNote(
            category=parse_enum(StatutoryCategory, source.category, "法定カテゴリ"),
            text=CounselingNote(required_text(source.text, "記載内容")),
        )
        for source in sources
    )


def build_soap(source: SoapInput) -> SoapRecord:
    """SOAPを構成する。"""
    return SoapRecord(
        subjective=_build_notes(source.subjective),
        objective=_build_notes(source.objective),
        assessment=_build_notes(source.assessment),
        plan=_build_notes(source.plan),
    )


def build_residual_drug(source: ResidualDrugInput) -> ResidualDrugRecord:
    """残薬状況を構成する。"""
    reason = to_optional_text(source.reason)
    return ResidualDrugRecord(
        has_residual_drugs=source.has_residual_drugs,
        quantity=(
            ResidualDrugQuantity(source.quantity)
            if source.quantity is not None
            else None
        ),
        reason=ResidualDrugReason(reason) if reason is not None else None,
    )


def build_handbook_status(source: HandbookStatusInput) -> HandbookStatus:
    """お薬手帳の活用状況を構成する。"""
    not_presented_reason = to_optional_text(source.not_presented_reason)
    consolidation_reason = to_optional_text(
        source.multiple_handbooks_not_consolidated_reason
    )
    return HandbookStatus(
        presented=source.presented,
        not_presented_reason=(
            HandbookNotPresentedReason(not_presented_reason)
            if not_presented_reason is not None
            else None
        ),
        guidance_provided=source.guidance_provided,
        multiple_handbooks_not_consolidated_reason=(
            HandbookConsolidationReason(consolidation_reason)
            if consolidation_reason is not None
            else None
        ),
    )


def _build_family_pharmacist(
    source: ProfileUpdateInput,
) -> FamilyPharmacistIntent | None:
    """かかりつけ薬剤師の同意を構成する。両方揃っていなければ受け付けない。"""
    staff_id = to_optional_text(source.family_pharmacist_id)
    agreed_on: date | None = source.family_pharmacist_agreed_on
    if staff_id is None and agreed_on is None:
        return None
    if staff_id is None or agreed_on is None:
        raise DomainValidationError(
            "かかりつけ薬剤師の同意は、薬剤師と同意日の両方を指定してください。"
        )
    return FamilyPharmacistIntent(
        pharmacist_id=StaffId.parse(staff_id), agreed_on=agreed_on
    )


def build_profile_updates(source: ProfileUpdateInput | None) -> ProfileUpdateIntents:
    """頭書きへの差分を構成する。"""
    if source is None:
        return ProfileUpdateIntents()
    lifestyle_note = to_optional_text(source.lifestyle_note)
    generic_preference = to_optional_text(source.generic_preference)
    return ProfileUpdateIntents(
        new_allergies=tuple(
            NewAllergyIntent(
                allergen=AllergenName(required_text(item.allergen, "アレルゲン")),
                reaction=AllergyReaction(required_text(item.reaction, "症状")),
                severity=parse_enum(AllergySeverity, item.severity, "重篤度"),
            )
            for item in source.new_allergies
        ),
        new_adverse_reactions=tuple(
            NewAdverseReactionIntent(
                medicine_name=MedicineName(
                    required_text(item.medicine_name, "医薬品名")
                ),
                symptom=AdverseReactionSymptom(
                    required_text(item.symptom, "副作用症状")
                ),
                occurred_on=item.occurred_on,
            )
            for item in source.new_adverse_reactions
        ),
        new_conditions=tuple(
            NewConditionIntent(
                condition_name=ConditionName(
                    required_text(item.condition_name, "疾患名")
                ),
                condition_status=parse_enum(
                    ConditionStatus, item.condition_status, "疾患の状態"
                ),
                is_contraindication_target=item.is_contraindication_target,
            )
            for item in source.new_conditions
        ),
        new_concurrent_medications=tuple(
            NewConcurrentMedicationIntent(
                medicine_name=MedicineName(required_text(item.medicine_name, "薬品名")),
                category=parse_enum(ConcurrentCategory, item.category, "併用薬の分類"),
                started_on=item.started_on,
                prescriber_institution=_institution_or_none(
                    item.prescriber_institution
                ),
            )
            for item in source.new_concurrent_medications
        ),
        stopped_concurrent_medications=tuple(
            StopConcurrentMedicationIntent(
                medicine_name=MedicineName(required_text(item.medicine_name, "薬品名")),
                ended_on=item.ended_on,
            )
            for item in source.stopped_concurrent_medications
        ),
        lifestyle_update=(
            LifestyleUpdateIntent(note=LifestyleNote(lifestyle_note))
            if lifestyle_note is not None
            else None
        ),
        generic_preference_update=(
            GenericPreferenceIntent(
                preference=parse_enum(
                    GenericPreferenceType, generic_preference, "後発医薬品への意向"
                )
            )
            if generic_preference is not None
            else None
        ),
        family_pharmacist_update=_build_family_pharmacist(source),
    )


def _institution_or_none(raw: str | None) -> MedicalInstitutionName | None:
    """処方元医療機関名を構成する。空文字は未指定として扱う。"""
    value = to_optional_text(raw)
    return MedicalInstitutionName(value) if value is not None else None


async def load_record_or_raise(
    repository: MedicationHistoryRepository,
    *,
    corporate_id: CorporateId,
    record_id: MedicationHistoryRecordId,
) -> MedicationHistoryRecord:
    """指定法人の薬歴を取得し、存在しなければ404相当を送出する。"""
    record = await repository.get(corporate_id=corporate_id, record_id=record_id)
    if record is None:
        raise MedicationHistoryNotFoundError()
    return record
