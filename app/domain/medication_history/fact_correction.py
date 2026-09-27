"""確定後の薬歴事実訂正と、原本から再生した有効値。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.domain.medication_history.primitives import (
    CounselingMethod,
    CounselingTimestamp,
    FactCorrectionTimestamp,
    FinalizationDelayReason,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    FamilyPharmacistIntent,
    GenericPreferenceIntent,
    HandbookStatus,
    LifestyleUpdateIntent,
    NewAdverseReactionIntent,
    NewAllergyIntent,
    NewConcurrentMedicationIntent,
    NewConditionIntent,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    RetractAdverseReactionIntent,
    RetractAllergyIntent,
    RetractConditionIntent,
    StopConcurrentMedicationIntent,
    UpdateConditionStatusIntent,
)
from app.domain.staff.primitives import StaffId

FACT_FIELD_TYPES: Final[dict[str, type[object]]] = {
    "counselor_id": StaffId,
    "counseled_at": CounselingTimestamp,
    "method": CounselingMethod,
    "handbook_status": HandbookStatus,
    "residual_drug": ResidualDrugRecord,
    "information_sheet_provided": bool,
    "source_system": MedicationHistorySourceSystem,
    "delay_reason": FinalizationDelayReason,
    "review_result": MedicationHistoryReviewResult,
    "profile_updates.lifestyle_update": LifestyleUpdateIntent,
    "profile_updates.generic_preference_update": GenericPreferenceIntent,
    "profile_updates.family_pharmacist_update": FamilyPharmacistIntent,
}

FACT_ARRAY_TYPES: Final[dict[str, type[object]]] = {
    "profile_updates.new_allergies": NewAllergyIntent,
    "profile_updates.retracted_allergies": RetractAllergyIntent,
    "profile_updates.new_adverse_reactions": NewAdverseReactionIntent,
    "profile_updates.retracted_adverse_reactions": RetractAdverseReactionIntent,
    "profile_updates.new_conditions": NewConditionIntent,
    "profile_updates.updated_conditions": UpdateConditionStatusIntent,
    "profile_updates.retracted_conditions": RetractConditionIntent,
    "profile_updates.new_concurrent_medications": NewConcurrentMedicationIntent,
    "profile_updates.stopped_concurrent_medications": StopConcurrentMedicationIntent,
    "additional_notes": CategorizedNote,
    "billing_additions": BillingAddition,
}


@dataclass(frozen=True, kw_only=True)
class FactElement:
    """原本または訂正で追加された配列要素。"""

    id: str
    value: object


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryFactCorrection:
    """原本を変更せず積み上げる一件の訂正。"""

    id: str
    target: str
    field_name: str
    operation: str
    before: object | None
    after: object | None
    reason: str
    corrected_by: StaffId
    recorded_at: FactCorrectionTimestamp
    element_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class EffectiveMedicationHistoryFacts:
    """原本と訂正列から再生した現在有効な薬歴事実。"""

    counselor_id: StaffId | None
    counseled_at: CounselingTimestamp | None
    method: CounselingMethod | None
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None
    profile_updates: ProfileUpdateIntents
    additional_notes: tuple[CategorizedNote, ...]
    billing_additions: tuple[BillingAddition, ...]
    source_system: MedicationHistorySourceSystem | None
    delay_reason: FinalizationDelayReason | None
    review_result: MedicationHistoryReviewResult | None
