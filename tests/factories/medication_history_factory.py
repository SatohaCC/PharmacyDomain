"""薬歴テストで共有する組み立てヘルパー。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
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
    FinalizationDelayReason,
    FinalizedTimestamp,
    FollowUpId,
    GenericPreferenceType,
    HandbookNotPresentedReason,
    LifestyleNote,
    MedicationHistoryImportTimestamp,
    MedicationHistoryReviewResult,
    MedicationHistoryReviewTimestamp,
    MedicationHistorySourceSystem,
    PhysicianName,
    PrescriberActionType,
    RetractionReason,
    StatutoryCategory,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportId,
    TracingReportResponseContent,
    TracingReportTimestamp,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    FollowUpRecord,
    GenericPreferenceIntent,
    HandbookStatus,
    LabeledNote,
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
    SoapRecord,
    StatutoryInquiryRecord,
    StatutoryPharmacistName,
    StatutoryRecordSource,
    StopConcurrentMedicationIntent,
    TracingReport,
    TracingReportResponse,
    UpdateConditionStatusIntent,
)
from app.domain.patient.primitives import PatientBirthDate, PatientId
from app.domain.prescription.primitives import (
    InquiryNumber,
    MedicalInstitutionAddressLine,
    MedicalInstitutionName,
    PrescriptionId,
    PrescriptionIssuedDate,
)
from app.domain.shared.medicine import MedicineName
from app.domain.shared.person_name import PersonNames
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

COUNSELED_AT = datetime(2026, 8, 24, 5, 0, tzinfo=UTC)
STARTED_ON = date(2026, 8, 1)
BIRTH_DATE = date(1960, 4, 2)
ISSUED_DATE = date(2026, 8, 23)


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


def create_retract_allergy_intent(
    allergen: str = "ペニシリン系",
    reason: str | None = "患者申し出による誤登録の修正。",
) -> RetractAllergyIntent:
    """アレルギー歴取消の差分を組み立てる。"""
    return RetractAllergyIntent(
        allergen=AllergenName(allergen),
        reason=RetractionReason(reason) if reason is not None else None,
    )


def create_retract_adverse_reaction_intent(
    medicine_name: str = "ロキソプロフェンＮａ錠６０ｍｇ",
    reason: str | None = "精査の結果、副作用ではなく一過性の胃炎と判明したため。",
) -> RetractAdverseReactionIntent:
    """副作用歴取消の差分を組み立てる。"""
    return RetractAdverseReactionIntent(
        medicine_name=MedicineName(medicine_name),
        reason=RetractionReason(reason) if reason is not None else None,
    )


def create_update_condition_status_intent(
    condition_name: str = "緑内障",
    new_status: ConditionStatus = ConditionStatus.RESOLVED,
    *,
    is_contraindication_target: bool | None = False,
) -> UpdateConditionStatusIntent:
    """疾患状態更新の差分を組み立てる。"""
    return UpdateConditionStatusIntent(
        condition_name=ConditionName(condition_name),
        new_status=new_status,
        is_contraindication_target=is_contraindication_target,
    )


def create_retract_condition_intent(
    condition_name: str = "緑内障",
    reason: str | None = "他科受診時の誤認により誤登録されたため。",
) -> RetractConditionIntent:
    """疾患取消の差分を組み立てる。"""
    return RetractConditionIntent(
        condition_name=ConditionName(condition_name),
        reason=RetractionReason(reason) if reason is not None else None,
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
    information_sheet_provided: bool | None = False,
    soap: SoapRecord | None = None,
    handbook_status: HandbookStatus | None = None,
    residual_drug: ResidualDrugRecord | None = None,
    profile_updates: ProfileUpdateIntents | None = None,
    additional_notes: tuple[CategorizedNote, ...] = (),
    billing_additions: tuple[BillingAddition, ...] = (),
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
        information_sheet_provided=information_sheet_provided,
        profile_updates=profile_updates,
        additional_notes=additional_notes,
        billing_additions=billing_additions,
    )


def finalize_record_with_review(
    record: MedicationHistoryRecord,
    *,
    review_result: MedicationHistoryReviewResult = MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    counselor_id: StaffId | None = None,
    counseled_at: CounselingTimestamp | None = None,
    finalized_at: FinalizedTimestamp | None = None,
    finalized_by: StaffId | None = None,
    delay_reason: FinalizationDelayReason | None = None,
    reviewed_by: StaffId | None = None,
    reviewed_at: MedicationHistoryReviewTimestamp | None = None,
) -> MedicationHistoryRecord:
    """レビュー入力を明示して薬歴を確定するテストヘルパー。"""
    actual_counselor_id = counselor_id or record.counselor_id
    actual_counseled_at = counseled_at or record.counseled_at
    actual_reviewed_by = reviewed_by or actual_counselor_id or StaffId.generate()
    actual_reviewed_at = (
        reviewed_at
        or (
            MedicationHistoryReviewTimestamp(actual_counseled_at.value)
            if actual_counseled_at is not None
            else None
        )
        or MedicationHistoryReviewTimestamp(COUNSELED_AT)
    )
    return record.finalize(
        counselor_id=actual_counselor_id,
        counseled_at=actual_counseled_at,
        finalized_at=finalized_at,
        finalized_by=finalized_by,
        delay_reason=delay_reason,
        review_result=review_result,
        reviewed_by=actual_reviewed_by,
        reviewed_at=actual_reviewed_at,
    )


def create_nsips_draft_record(
    *,
    imported_at: datetime = datetime(2026, 8, 24, 4, 0, tzinfo=UTC),
    ready_to_finalize: bool = False,
    corporate_id: CorporateId | None = None,
    store_id: StoreId | None = None,
    patient_id: PatientId | None = None,
    dispensing_id: DispensingId | None = None,
    prescription_id: PrescriptionId | None = None,
) -> MedicationHistoryRecord:
    """実指導情報のない、NSIPS取込由来の下書きを組み立てる。"""
    existing = create_record(
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=patient_id,
        dispensing_id=dispensing_id,
        prescription_id=prescription_id,
    )
    imported_record = replace(
        existing,
        counselor_id=None,
        counseled_at=None,
        method=None,
        handbook_status=None,
        residual_drug=None,
        information_sheet_provided=None,
        source_system=MedicationHistorySourceSystem("NSIPS"),
        imported_at=MedicationHistoryImportTimestamp(imported_at),
    )
    if not ready_to_finalize:
        return imported_record
    return replace(
        imported_record,
        method=existing.method,
        handbook_status=existing.handbook_status,
        residual_drug=existing.residual_drug,
        information_sheet_provided=existing.information_sheet_provided,
    )


def create_follow_up(
    *,
    follow_up_id: FollowUpId | None = None,
    counselor_id: StaffId | None = None,
    followed_up_at: datetime | None = None,
    method: CounselingMethod = CounselingMethod.TELEPHONE,
    soap: SoapRecord | None = None,
    handbook_status: HandbookStatus | None = None,
    residual_drug: ResidualDrugRecord | None = None,
    information_sheet_provided: bool = False,
    profile_updates: ProfileUpdateIntents | None = None,
    additional_notes: tuple[CategorizedNote, ...] = (),
) -> FollowUpRecord:
    """服薬期間中のフォローアップ記録を組み立てる。"""
    return FollowUpRecord(
        id=follow_up_id if follow_up_id is not None else FollowUpId.generate(),
        counselor_id=counselor_id if counselor_id is not None else StaffId.generate(),
        followed_up_at=CounselingTimestamp(
            followed_up_at
            if followed_up_at is not None
            else datetime(2026, 8, 27, 5, 0, tzinfo=UTC)
        ),
        method=method,
        soap=soap
        if soap is not None
        else create_soap(subjective="服用後の体調に問題なし。"),
        handbook_status=handbook_status
        if handbook_status is not None
        else create_handbook_status(),
        residual_drug=residual_drug
        if residual_drug is not None
        else ResidualDrugRecord.none_remaining(),
        information_sheet_provided=information_sheet_provided,
        profile_updates=profile_updates
        if profile_updates is not None
        else ProfileUpdateIntents(),
        additional_notes=additional_notes,
    )


def create_person_names(
    last_name: str = "山田",
    first_name: str = "太郎",
    last_name_kana: str = "ヤマダ",
    first_name_kana: str = "タロウ",
) -> PersonNames:
    """漢字とカナの氏名一式を組み立てる。"""
    return PersonNames.create(
        last_name=last_name,
        first_name=first_name,
        last_name_kana=last_name_kana,
        first_name_kana=first_name_kana,
    )


def create_pharmacist_name(
    staff_id: StaffId,
    last_name: str = "鈴木",
    first_name: str = "花子",
) -> StatutoryPharmacistName:
    """調剤録へ記載する薬剤師1名の氏名を組み立てる。"""
    return StatutoryPharmacistName(
        staff_id=staff_id,
        names=create_person_names(
            last_name=last_name,
            first_name=first_name,
            last_name_kana="スズキ",
            first_name_kana="ハナコ",
        ),
    )


def create_inquiry(
    number: int = 1,
    *,
    has_response: bool = True,
) -> StatutoryInquiryRecord:
    """疑義照会1件の写しを組み立てる。"""
    return StatutoryInquiryRecord(
        inquiry_number=InquiryNumber(number), has_response=has_response
    )


def create_statutory_source(
    *,
    patient_id: PatientId,
    prescription_id: PrescriptionId,
    pharmacist_ids: tuple[StaffId, ...] = (),
    pharmacist_names: tuple[StatutoryPharmacistName, ...] | None = None,
    patient_birth_date: date | None = BIRTH_DATE,
    issued_date: date = ISSUED_DATE,
    institution_name: str = "医療法人社団さくら内科クリニック",
    institution_address: str | None = "東京都千代田区丸の内1-1-1",
    inquiries: tuple[StatutoryInquiryRecord, ...] = (),
) -> StatutoryRecordSource:
    """調剤録の記載事項のスナップショットを組み立てる。

    既定では欠落の無い状態を作る。個別のケースは欠けさせたい項目だけを指定する。
    ``pharmacist_ids`` を渡すと、そのスタッフ全員の氏名を引ける状態にする。
    """
    return StatutoryRecordSource(
        patient_id=patient_id,
        patient_names=create_person_names(),
        patient_birth_date=(
            PatientBirthDate(patient_birth_date)
            if patient_birth_date is not None
            else None
        ),
        pharmacist_names=(
            pharmacist_names
            if pharmacist_names is not None
            else tuple(create_pharmacist_name(staff_id) for staff_id in pharmacist_ids)
        ),
        prescription_id=prescription_id,
        prescription_issued_date=PrescriptionIssuedDate(issued_date),
        prescriber_names=create_person_names(
            last_name="佐藤",
            first_name="一郎",
            last_name_kana="サトウ",
            first_name_kana="イチロウ",
        ).kanji,
        medical_institution_name=MedicalInstitutionName(institution_name),
        medical_institution_address=(
            MedicalInstitutionAddressLine(institution_address)
            if institution_address is not None
            else None
        ),
        inquiries=inquiries,
    )


def create_record_for(
    dispensing: DispensingProcess,
    *,
    counselor_id: StaffId | None = None,
    soap: SoapRecord | None = None,
    finalized: bool = True,
) -> MedicationHistoryRecord:
    """指定の調剤セッションに対応する薬歴を組み立てる。

    法人・店舗・患者・処方箋は調剤セッションから取る。ユースケースも同じ取り方を
    するので、ここで取り違えた組み合わせを既定にしない。
    """
    record = create_record(
        corporate_id=dispensing.corporate_id,
        store_id=dispensing.store_id,
        patient_id=dispensing.patient_id,
        dispensing_id=dispensing.id,
        prescription_id=dispensing.prescription_id,
        counselor_id=counselor_id,
        soap=soap,
    )
    return finalize_record_with_review(record) if finalized else record


def create_tracing_report(
    *,
    report_id: TracingReportId | None = None,
    reporter_id: StaffId | None = None,
    provided_at: datetime | None = None,
    medical_institution_name: str = "総合医療センター",
    physician_name: str = "山田太郎",
    category: TracingReportCategory = TracingReportCategory.RESIDUAL_DRUG,
    fee_category: TracingReportFeeCategory = TracingReportFeeCategory.FEE_2,
    delivery_method: TracingReportDeliveryMethod = TracingReportDeliveryMethod.FAX,
    content: str = "残薬が14日分確認されたため、次回処方時の日数調整をご検討ください。",
    follow_up_id: FollowUpId | None = None,
    response: TracingReportResponse | None = None,
) -> TracingReport:
    """トレーシングレポートのテストデータを組み立てる。"""
    return TracingReport(
        id=report_id or TracingReportId.generate(),
        reporter_id=reporter_id or StaffId.generate(),
        provided_at=TracingReportTimestamp(provided_at or COUNSELED_AT),
        medical_institution_name=MedicalInstitutionName(medical_institution_name),
        physician_name=PhysicianName(physician_name),
        category=category,
        fee_category=fee_category,
        delivery_method=delivery_method,
        content=TracingReportContent(content),
        follow_up_id=follow_up_id,
        response=response,
    )


def create_tracing_report_response(
    *,
    responded_at: datetime | None = None,
    action_type: PrescriberActionType = PrescriberActionType.AGREED_REFLECT_NEXT,
    content: str = "了解しました。次回処方時に14日分減量して処方します。",
    received_by: StaffId | None = None,
    acknowledged_physician_name: str | None = None,
) -> TracingReportResponse:
    """トレーシングレポート返答のテストデータを組み立てる。"""
    return TracingReportResponse(
        responded_at=TracingReportTimestamp(responded_at or COUNSELED_AT),
        action_type=action_type,
        content=TracingReportResponseContent(content),
        received_by=received_by or StaffId.generate(),
        acknowledged_physician_name=(
            PhysicianName(acknowledged_physician_name)
            if acknowledged_physician_name is not None
            else None
        ),
    )
