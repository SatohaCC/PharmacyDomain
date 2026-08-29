"""薬歴テストで共有する組み立てヘルパー。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.base.domain.medicine import MedicineName
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history import (
    AdverseReactionSymptom,
    AllergenName,
    AllergyReaction,
    AllergySeverity,
    ConcurrentCategory,
    ConditionName,
    ConditionStatus,
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    GenericPreferenceIntent,
    GenericPreferenceType,
    HandbookNotPresentedReason,
    HandbookStatus,
    LabeledNote,
    LifestyleNote,
    LifestyleUpdateIntent,
    MedicationHistoryRecord,
    NewAdverseReactionIntent,
    NewAllergyIntent,
    NewConcurrentMedicationIntent,
    NewConditionIntent,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
    StatutoryCategory,
    StopConcurrentMedicationIntent,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

COUNSELED_AT = datetime(2026, 8, 24, 5, 0, tzinfo=UTC)
STARTED_ON = date(2026, 8, 1)


def create_note(
    text: str = "服薬状況に問題なし。",
    category: StatutoryCategory = StatutoryCategory.GENERAL,
) -> LabeledNote:
    """ラベル付きの記載を1件組み立てる。"""
    return LabeledNote(category=category, text=CounselingNote(text))


def create_soap(
    *,
    subjective: str = "飲み忘れは週に1回程度とのこと。",
    objective: str = "血圧手帳の記録は良好。",
    assessment: str = "アドヒアランスはおおむね良好。",
    plan: str = "次回まで服薬時刻の固定を提案。",
) -> SoapRecord:
    """S/O/A/P がすべて埋まったSOAPを組み立てる。"""
    return SoapRecord(
        subjective=(create_note(subjective, StatutoryCategory.MEDICATION_ADHERENCE),),
        objective=(create_note(objective),),
        assessment=(create_note(assessment),),
        plan=(create_note(plan, StatutoryCategory.FUTURE_PLAN_CAUTION),),
    )


def create_handbook_status(*, presented: bool = True) -> HandbookStatus:
    """お薬手帳の活用状況を組み立てる。"""
    if presented:
        return HandbookStatus(presented=True)
    return HandbookStatus(
        presented=False,
        not_presented_reason=HandbookNotPresentedReason("持参を忘れたとのこと。"),
        guidance_provided=True,
    )


def create_allergy_intent(
    allergen: str = "ペニシリン系",
    reaction: str = "皮疹",
    severity: AllergySeverity = AllergySeverity.MODERATE,
) -> NewAllergyIntent:
    """アレルギー歴の差分を組み立てる。"""
    return NewAllergyIntent(
        allergen=AllergenName(allergen),
        reaction=AllergyReaction(reaction),
        severity=severity,
    )


def create_adverse_reaction_intent(
    medicine_name: str = "ロキソプロフェンＮａ錠６０ｍｇ",
    symptom: str = "胃痛",
) -> NewAdverseReactionIntent:
    """副作用歴の差分を組み立てる。"""
    return NewAdverseReactionIntent(
        medicine_name=MedicineName(medicine_name),
        symptom=AdverseReactionSymptom(symptom),
    )


def create_condition_intent(
    condition_name: str = "緑内障",
    *,
    is_contraindication_target: bool = True,
) -> NewConditionIntent:
    """疾患の差分を組み立てる。"""
    return NewConditionIntent(
        condition_name=ConditionName(condition_name),
        condition_status=ConditionStatus.ONGOING,
        is_contraindication_target=is_contraindication_target,
    )


def create_concurrent_intent(
    medicine_name: str = "市販の総合感冒薬",
    category: ConcurrentCategory = ConcurrentCategory.OTC,
    started_on: date = STARTED_ON,
) -> NewConcurrentMedicationIntent:
    """併用薬開始の差分を組み立てる。"""
    return NewConcurrentMedicationIntent(
        medicine_name=MedicineName(medicine_name),
        category=category,
        started_on=started_on,
    )


def create_stop_intent(
    medicine_name: str = "市販の総合感冒薬",
    ended_on: date = date(2026, 8, 20),
) -> StopConcurrentMedicationIntent:
    """併用薬終了の差分を組み立てる。"""
    return StopConcurrentMedicationIntent(
        medicine_name=MedicineName(medicine_name),
        ended_on=ended_on,
    )


def create_lifestyle_intents(
    note: str = "毎朝グレープフルーツジュースを飲む習慣あり。",
) -> ProfileUpdateIntents:
    """生活像だけを更新する差分を組み立てる。"""
    return ProfileUpdateIntents(
        lifestyle_update=LifestyleUpdateIntent(note=LifestyleNote(note))
    )


def create_generic_preference_intents(
    preference: GenericPreferenceType = GenericPreferenceType.ACCEPTS,
) -> ProfileUpdateIntents:
    """後発医薬品意向だけを更新する差分を組み立てる。"""
    return ProfileUpdateIntents(
        generic_preference_update=GenericPreferenceIntent(preference=preference)
    )


def create_record(
    *,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
    patient_id: PatientId | None = None,
    dispensing_id: DispensingId | None = None,
    prescription_id: PrescriptionId | None = None,
    counselor_id: StaffId | None = None,
    counseled_at: datetime = COUNSELED_AT,
    method: CounselingMethod = CounselingMethod.FACE_TO_FACE,
    soap: SoapRecord | None = None,
    handbook_status: HandbookStatus | None = None,
    residual_drug: ResidualDrugRecord | None = None,
    profile_updates: ProfileUpdateIntents | None = None,
) -> MedicationHistoryRecord:
    """薬歴を下書き状態で組み立てる。"""
    return MedicationHistoryRecord.start(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        store_id=store_id if store_id is not None else StoreId.generate(),
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        dispensing_id=dispensing_id
        if dispensing_id is not None
        else DispensingId.generate(),
        prescription_id=prescription_id
        if prescription_id is not None
        else PrescriptionId.generate(),
        counselor_id=counselor_id if counselor_id is not None else StaffId.generate(),
        counseled_at=CounselingTimestamp(counseled_at),
        method=method,
        soap=soap if soap is not None else create_soap(),
        handbook_status=handbook_status
        if handbook_status is not None
        else create_handbook_status(),
        residual_drug=residual_drug
        if residual_drug is not None
        else ResidualDrugRecord.none_remaining(),
        profile_updates=profile_updates,
    )
