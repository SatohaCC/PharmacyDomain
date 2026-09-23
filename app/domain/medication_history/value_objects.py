"""MedicationHistoryコンテキストの複合 Value Object。

頭書きの要素（アレルギー歴・副作用歴・既往歴・併用薬・生活像・後発品意向・
かかりつけ薬剤師）は**すべて ``ProfileProvenance`` を持つ**。1つでも由来の無い
要素があると、頭書きが薬歴から再構築できなくなり「投影である」という前提が崩れる。

薬歴が頭書きへ加える差分は ``ProfileUpdateIntents`` として薬歴側が持つ。
由来（どの薬歴か・誰が・いつ）は投影時に薬歴から埋まるので、Intent は
由来を持たない。持たせると、薬歴と食い違う由来を書ける余地ができる。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from typing import ClassVar, Self

from app.domain.foundation.entity import Entity
from app.domain.foundation.value_object import ValueObject
from app.domain.medication_history.exceptions import (
    ConcurrentMedicationPeriodInvertedError,
    HandbookGuidanceRequiredError,
    HandbookReasonNotAllowedError,
    ResidualDrugDetailNotAllowedError,
    ResidualDrugDetailRequiredError,
    SoapContentRequiredError,
    StatutoryItemAssessedTwiceError,
    StatutoryItemNotAssessedError,
    TracingReportAlreadyRespondedError,
    TracingReportResponseDateBeforeProvidedError,
)
from app.domain.medication_history.primitives import (
    AdverseReactionSymptom,
    AllergenName,
    AllergyReaction,
    AllergySeverity,
    AmendmentReason,
    AmendmentTimestamp,
    BillingAdditionCode,
    BillingAdditionName,
    ConcurrentCategory,
    ConditionName,
    ConditionStatus,
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    ExternalCorrectionTimestamp,
    FollowUpId,
    GenericPreferenceType,
    HandbookConsolidationReason,
    HandbookNotPresentedReason,
    LifestyleNote,
    MajorCategoryCode,
    MajorCategoryName,
    MedicationHistoryRecordId,
    MedicationHistorySourceSystem,
    MediumCategoryCode,
    MediumCategoryName,
    PhysicianName,
    PrescriberActionType,
    ResidualDrugQuantity,
    ResidualDrugReason,
    RetractionReason,
    StatutoryCategory,
    StatutoryDispensingRecordItem,
    StatutoryItemState,
    StatutoryRecordBlocker,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportId,
    TracingReportResponseContent,
    TracingReportTimestamp,
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
from app.domain.shared.person_name import PersonName, PersonNames
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class ProfileProvenance(ValueObject):
    """頭書きの各要素が「どの薬歴に基づくか」の根拠。

    3項目とも必須にする。1つでも欠けると、頭書きを薬歴から再構築したときに
    その要素だけ由来が復元できず、投影であることが成立しなくなる。
    """

    source_record_id: MedicationHistoryRecordId
    recorded_by: StaffId
    recorded_on: date

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_record_id": "由来の薬歴ID",
        "recorded_by": "登録した薬剤師",
        "recorded_on": "登録日",
    }


# --------------------------------------------------------------------------
# 区分定義（大区分・中区分）
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class MajorCategoryDefinition(ValueObject):
    """大区分の定義。"""

    code: MajorCategoryCode
    name: MajorCategoryName
    display_order: int
    is_enabled: bool = True

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code": "大区分コード",
        "name": "大区分名",
        "display_order": "表示順",
        "is_enabled": "有効フラグ",
    }


@dataclass(frozen=True, kw_only=True)
class MediumCategoryDefinition(ValueObject):
    """中区分の定義（大区分に紐づく）。"""

    code: MediumCategoryCode
    major_category_code: MajorCategoryCode
    name: MediumCategoryName
    display_order: int
    is_required: bool = False
    is_enabled: bool = True

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code": "中区分コード",
        "major_category_code": "親大区分コード",
        "name": "中区分名",
        "display_order": "表示順",
        "is_required": "確定時必須フラグ",
        "is_enabled": "有効フラグ",
    }


@dataclass(frozen=True, kw_only=True)
class CategorizedNote(ValueObject):
    """大区分・中区分に紐づく記載メモ1件。"""

    major_category_code: MajorCategoryCode
    medium_category_code: MediumCategoryCode
    text: CounselingNote
    statutory_category: StatutoryCategory = StatutoryCategory.GENERAL

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "major_category_code": "大区分コード",
        "medium_category_code": "中区分コード",
        "text": "記載内容",
        "statutory_category": "法定カテゴリ",
    }

    @property
    def has_content(self) -> bool:
        """本文が空でないか。"""
        return bool(self.text.value.strip())


# --------------------------------------------------------------------------
# SOAP
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class LabeledNote(ValueObject):
    """法定記載事項のラベルを付けた自由記述1件。"""

    category: StatutoryCategory
    text: CounselingNote

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "category": "法定カテゴリ",
        "text": "記載内容",
    }

    @property
    def has_content(self) -> bool:
        """本文が空でないか。"""
        return bool(self.text.value.strip())


@dataclass(frozen=True, kw_only=True)
class SoapRecord(ValueObject):
    """SOAP形式の服薬指導記録。

    各セクションはラベル付きメモの列。確定時に全セクションが1件以上の
    記載を持つことを ``MedicationHistoryRecord.finalize()`` が要求する。
    """

    subjective: tuple[LabeledNote, ...] = ()
    objective: tuple[LabeledNote, ...] = ()
    assessment: tuple[LabeledNote, ...] = ()
    plan: tuple[LabeledNote, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "subjective": "S（主観的情報）",
        "objective": "O（客観的情報）",
        "assessment": "A（評価）",
        "plan": "P（計画）",
    }

    @property
    def has_content(self) -> bool:
        """S/O/A/P のいずれか1つ以上に空でない記載があるか。"""
        return any(
            any(note.has_content for note in getattr(self, field_name))
            for field_name in ("subjective", "objective", "assessment", "plan")
        )

    @property
    def is_empty(self) -> bool:
        """S/O/A/P の全セクションに記載が無い（白紙である）か。"""
        return not self.has_content

    @property
    def empty_section_label(self) -> str | None:
        """記載が1件も無いセクションの日本語名。すべて埋まっていれば ``None``。"""
        for field_name in ("subjective", "objective", "assessment", "plan"):
            notes: tuple[LabeledNote, ...] = getattr(self, field_name)
            if not any(note.has_content for note in notes):
                return self._FIELD_LABELS[field_name]
        return None

    def notes_of(self, category: StatutoryCategory) -> tuple[LabeledNote, ...]:
        """指定した法定カテゴリの記載を、SOAP横断で抽出する。

        個別指導で「体調変化の確認はどこか」と問われたときに使う。
        """
        return tuple(
            note
            for section in (
                self.subjective,
                self.objective,
                self.assessment,
                self.plan,
            )
            for note in section
            if note.category is category
        )


# --------------------------------------------------------------------------
# 法定記載事項（残薬・お薬手帳）
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ResidualDrugRecord(ValueObject):
    """残薬状況（法定記載事項ウ（ホ））。

    「残薬がないときは、その旨を記載すること」と明示されているため、この値は
    **必須**であり、「残薬なし」を表せる。``Optional`` にすると「聞き忘れ」と
    「残薬なし」が同じ ``None`` になる。
    """

    has_residual_drugs: bool
    quantity: ResidualDrugQuantity | None = None
    reason: ResidualDrugReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "has_residual_drugs": "残薬の有無",
        "quantity": "残薬数量",
        "reason": "残薬の発生理由",
    }

    def validate(self) -> None:
        """残薬の有無と詳細の整合を検証する。"""
        if self.has_residual_drugs:
            if self.quantity is None or self.reason is None:
                raise ResidualDrugDetailRequiredError()
            return
        if self.quantity is not None or self.reason is not None:
            raise ResidualDrugDetailNotAllowedError()

    @classmethod
    def none_remaining(cls) -> Self:
        """残薬なしを記録する。"""
        return cls(has_residual_drugs=False)


@dataclass(frozen=True, kw_only=True)
class HandbookStatus(ValueObject):
    """お薬手帳の活用状況（法定記載事項ウ（ト））。

    「活用の有無」「活用しなかった理由」「患者への指導の有無」の3つは
    独立した情報であり、1つの列挙では表現できない。
    """

    presented: bool
    not_presented_reason: HandbookNotPresentedReason | None = None
    guidance_provided: bool | None = None
    multiple_handbooks_not_consolidated_reason: HandbookConsolidationReason | None = (
        None
    )

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "presented": "手帳活用の有無",
        "not_presented_reason": "未活用の理由",
        "guidance_provided": "患者への指導の有無",
        "multiple_handbooks_not_consolidated_reason": "複数手帳を統合しなかった理由",
    }

    def validate(self) -> None:
        """活用の有無と、理由・指導の記録の整合を検証する。"""
        if not self.presented:
            if self.not_presented_reason is None or self.guidance_provided is None:
                raise HandbookGuidanceRequiredError()
            return
        if self.not_presented_reason is not None:
            raise HandbookReasonNotAllowedError()


# --------------------------------------------------------------------------
# 頭書きの要素
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class AllergyRecord(ValueObject):
    """アレルギー歴（法定記載事項ウ（イ））。"""

    allergen: AllergenName
    reaction: AllergyReaction
    severity: AllergySeverity
    provenance: ProfileProvenance

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "allergen": "アレルゲン",
        "reaction": "症状",
        "severity": "重篤度",
        "provenance": "由来",
    }


@dataclass(frozen=True, kw_only=True)
class AdverseReactionRecord(ValueObject):
    """副作用歴（法定記載事項ウ（イ））。"""

    medicine_name: MedicineName
    symptom: AdverseReactionSymptom
    provenance: ProfileProvenance
    occurred_on: date | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "医薬品名",
        "symptom": "副作用症状",
        "provenance": "由来",
        "occurred_on": "発現時期",
    }


@dataclass(frozen=True, kw_only=True)
class MedicalConditionRecord(ValueObject):
    """既往歴・合併症・他科加療中の疾患（法定記載事項ウ（ロ））。"""

    condition_name: ConditionName
    condition_status: ConditionStatus
    is_contraindication_target: bool
    provenance: ProfileProvenance

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "condition_name": "疾患名",
        "condition_status": "疾患の状態",
        "is_contraindication_target": "禁忌対象",
        "provenance": "由来",
    }


@dataclass(frozen=True, kw_only=True)
class ConcurrentMedicationRecord(ValueObject):
    """併用薬（法定記載事項ウ（ハ））。

    **``is_active`` フィールドを持たない。** ``ended_on is None``（継続中）と
    ``is_active == True`` は同じ事実であり、2つ持てば必ず食い違う。有効・無効は
    :meth:`is_active_on` として**適用日を引数で受け取る全域関数**で判定する。
    遡及判定（過去のある日に併用していたか）は相互作用チェックで実際に要る。

    この禁止は子レコードのフィールドに関するものなので、集約ルートを見る
    ``tests/domain/test_lifecycle_dialects.py`` では検出できない。代わりに
    ``tests/domain/test_active_flag_placement.py`` が ``is_active`` を持つ
    クラスの一覧を固定して守る。
    """

    medicine_name: MedicineName
    category: ConcurrentCategory
    started_on: date
    provenance: ProfileProvenance
    prescriber_institution: MedicalInstitutionName | None = None
    ended_on: date | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "薬品名",
        "category": "併用薬の分類",
        "started_on": "開始日",
        "provenance": "由来",
        "prescriber_institution": "処方元医療機関",
        "ended_on": "終了日",
    }

    def validate(self) -> None:
        """終了日が開始日以降であることを検証する。"""
        if self.ended_on is not None and self.ended_on < self.started_on:
            raise ConcurrentMedicationPeriodInvertedError()

    def is_active_on(self, target_date: date) -> bool:
        """指定日に併用していたかを返す。終了日を含む閉区間で判定する。"""
        if target_date < self.started_on:
            return False
        return self.ended_on is None or target_date <= self.ended_on

    def close(self, ended_on: date) -> Self:
        """飲み切り・中止により併用が終わったことを記録する。"""
        return type(self)(
            medicine_name=self.medicine_name,
            category=self.category,
            started_on=self.started_on,
            provenance=self.provenance,
            prescriber_institution=self.prescriber_institution,
            ended_on=ended_on,
        )


@dataclass(frozen=True, kw_only=True)
class LifestyleProfile(ValueObject):
    """生活像と、相互作用が認められる飲食物の摂取状況。"""

    note: LifestyleNote
    provenance: ProfileProvenance

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "note": "生活像",
        "provenance": "由来",
    }


@dataclass(frozen=True, kw_only=True)
class GenericPreference(ValueObject):
    """後発医薬品の使用に関する患者の意向（法定記載事項ウ（イ））。"""

    preference: GenericPreferenceType
    provenance: ProfileProvenance

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "preference": "後発医薬品への意向",
        "provenance": "由来",
    }


@dataclass(frozen=True, kw_only=True)
class FamilyPharmacistAgreement(ValueObject):
    """かかりつけ薬剤師の同意。"""

    pharmacist_id: StaffId
    agreed_on: date
    provenance: ProfileProvenance

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "pharmacist_id": "かかりつけ薬剤師",
        "agreed_on": "同意日",
        "provenance": "由来",
    }


# --------------------------------------------------------------------------
# 頭書きへの差分（薬歴が持つ）
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class NewAllergyIntent(ValueObject):
    """薬歴で聞き取ったアレルギー歴。"""

    allergen: AllergenName
    reaction: AllergyReaction
    severity: AllergySeverity

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "allergen": "アレルゲン",
        "reaction": "症状",
        "severity": "重篤度",
    }


@dataclass(frozen=True, kw_only=True)
class NewAdverseReactionIntent(ValueObject):
    """薬歴で聞き取った副作用歴。"""

    medicine_name: MedicineName
    symptom: AdverseReactionSymptom
    occurred_on: date | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "医薬品名",
        "symptom": "副作用症状",
        "occurred_on": "発現時期",
    }


@dataclass(frozen=True, kw_only=True)
class NewConditionIntent(ValueObject):
    """薬歴で聞き取った疾患。"""

    condition_name: ConditionName
    condition_status: ConditionStatus
    is_contraindication_target: bool = False

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "condition_name": "疾患名",
        "condition_status": "疾患の状態",
        "is_contraindication_target": "禁忌対象",
    }


@dataclass(frozen=True, kw_only=True)
class RetractAllergyIntent(ValueObject):
    """薬歴で取り消したアレルギー歴（誤登録・否定）。"""

    allergen: AllergenName
    reason: RetractionReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "allergen": "アレルゲン",
        "reason": "取消理由",
    }


@dataclass(frozen=True, kw_only=True)
class RetractAdverseReactionIntent(ValueObject):
    """薬歴で取り消した副作用歴（誤登録・否定）。"""

    medicine_name: MedicineName
    reason: RetractionReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "医薬品名",
        "reason": "取消理由",
    }


@dataclass(frozen=True, kw_only=True)
class UpdateConditionStatusIntent(ValueObject):
    """薬歴で確認した疾患の状態変更（治癒・寛解・コントロール等）。"""

    condition_name: ConditionName
    new_status: ConditionStatus
    is_contraindication_target: bool | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "condition_name": "疾患名",
        "new_status": "新しい疾患状態",
        "is_contraindication_target": "禁忌対象の変更",
    }


@dataclass(frozen=True, kw_only=True)
class RetractConditionIntent(ValueObject):
    """薬歴で取り消した疾患情報（誤登録）。"""

    condition_name: ConditionName
    reason: RetractionReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "condition_name": "疾患名",
        "reason": "取消理由",
    }


@dataclass(frozen=True, kw_only=True)
class NewConcurrentMedicationIntent(ValueObject):
    """薬歴で聞き取った併用薬の開始。"""

    medicine_name: MedicineName
    category: ConcurrentCategory
    started_on: date
    prescriber_institution: MedicalInstitutionName | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "薬品名",
        "category": "併用薬の分類",
        "started_on": "開始日",
        "prescriber_institution": "処方元医療機関",
    }


@dataclass(frozen=True, kw_only=True)
class StopConcurrentMedicationIntent(ValueObject):
    """薬歴で聞き取った併用薬の終了。"""

    medicine_name: MedicineName
    ended_on: date

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "medicine_name": "薬品名",
        "ended_on": "終了日",
    }


@dataclass(frozen=True, kw_only=True)
class LifestyleUpdateIntent(ValueObject):
    """薬歴で聞き取った生活像の更新。"""

    note: LifestyleNote

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"note": "生活像"}


@dataclass(frozen=True, kw_only=True)
class GenericPreferenceIntent(ValueObject):
    """薬歴で確認した後発医薬品への意向。"""

    preference: GenericPreferenceType

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"preference": "後発医薬品への意向"}


@dataclass(frozen=True, kw_only=True)
class FamilyPharmacistIntent(ValueObject):
    """薬歴で締結したかかりつけ薬剤師の同意。"""

    pharmacist_id: StaffId
    agreed_on: date

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "pharmacist_id": "かかりつけ薬剤師",
        "agreed_on": "同意日",
    }


@dataclass(frozen=True, kw_only=True)
class ProfileUpdateIntents(ValueObject):
    """1回の服薬指導が頭書きへ加える差分の全体。

    ここに記録された差分をすべての薬歴について ``counseled_at`` 昇順に畳み込めば、
    頭書きは決定的に再構築できる。
    """

    new_allergies: tuple[NewAllergyIntent, ...] = ()
    retracted_allergies: tuple[RetractAllergyIntent, ...] = ()
    new_adverse_reactions: tuple[NewAdverseReactionIntent, ...] = ()
    retracted_adverse_reactions: tuple[RetractAdverseReactionIntent, ...] = ()
    new_conditions: tuple[NewConditionIntent, ...] = ()
    updated_conditions: tuple[UpdateConditionStatusIntent, ...] = ()
    retracted_conditions: tuple[RetractConditionIntent, ...] = ()
    new_concurrent_medications: tuple[NewConcurrentMedicationIntent, ...] = ()
    stopped_concurrent_medications: tuple[StopConcurrentMedicationIntent, ...] = ()
    lifestyle_update: LifestyleUpdateIntent | None = None
    generic_preference_update: GenericPreferenceIntent | None = None
    family_pharmacist_update: FamilyPharmacistIntent | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "new_allergies": "追加するアレルギー歴",
        "retracted_allergies": "取り消すアレルギー歴",
        "new_adverse_reactions": "追加する副作用歴",
        "retracted_adverse_reactions": "取り消す副作用歴",
        "new_conditions": "追加する疾患",
        "updated_conditions": "更新する疾患状態",
        "retracted_conditions": "取り消す疾患",
        "new_concurrent_medications": "追加する併用薬",
        "stopped_concurrent_medications": "終了する併用薬",
        "lifestyle_update": "生活像の更新",
        "generic_preference_update": "後発医薬品意向の更新",
        "family_pharmacist_update": "かかりつけ薬剤師の同意",
    }

    @property
    def is_empty(self) -> bool:
        """頭書きへの差分が1件も無いか。"""
        return not (
            self.new_allergies
            or self.retracted_allergies
            or self.new_adverse_reactions
            or self.retracted_adverse_reactions
            or self.new_conditions
            or self.updated_conditions
            or self.retracted_conditions
            or self.new_concurrent_medications
            or self.stopped_concurrent_medications
            or self.lifestyle_update is not None
            or self.generic_preference_update is not None
            or self.family_pharmacist_update is not None
        )


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryAmendment(ValueObject):
    """確定済薬歴への追記。

    元の記録を書き換えず、追記として積む。調剤録は3年間の保存義務があり、
    遡って書き換えられる記録は監査に耐えない。
    """

    amended_soap: SoapRecord
    reason: AmendmentReason
    amended_by: StaffId
    amended_at: AmendmentTimestamp

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "amended_soap": "修正後のSOAP",
        "reason": "追記理由",
        "amended_by": "追記者",
        "amended_at": "追記日時",
    }


@dataclass(frozen=True, kw_only=True)
class ExternalPrescriptionCorrection(ValueObject):
    """外部レセコン（Uファイル等）による処方訂正の監査証跡。

    確定済み薬歴の原本記録（SOAP、確定日時、確定者）は真正性保護のため不可逆凍結し、
    外部から発生した処方変更・調剤訂正の事実を本証跡として記録する。
    """

    correction_id: str
    corrected_at: ExternalCorrectionTimestamp
    source_document_number: str
    reason: str
    details: str | None = None
    acknowledged_at: ExternalCorrectionTimestamp | None = None
    acknowledged_by: StaffId | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "correction_id": "訂正ID",
        "corrected_at": "外部訂正日時",
        "source_document_number": "処方箋番号",
        "reason": "訂正理由",
        "details": "訂正詳細",
        "acknowledged_at": "確認日時",
        "acknowledged_by": "確認者",
    }

    @property
    def is_acknowledged(self) -> bool:
        """薬剤師によって確認（または追記により対処）されたか。"""
        return self.acknowledged_at is not None


@dataclass(frozen=True, eq=False, kw_only=True)
class FollowUpRecord(Entity[FollowUpId]):
    """服薬期間中のフォローアップ（調剤後フォロー）記録。

    固有の識別子（FollowUpId）で同一性を持つ集約内子エンティティ。
    """

    id: FollowUpId
    counselor_id: StaffId
    followed_up_at: CounselingTimestamp
    method: CounselingMethod | None
    soap: SoapRecord
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None = False
    source_system: MedicationHistorySourceSystem | None = None
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "フォローアップID",
        "counselor_id": "指導薬剤師",
        "followed_up_at": "フォローアップ日時",
        "method": "実施方法",
        "soap": "SOAP記録",
        "handbook_status": "お薬手帳確認",
        "residual_drug": "残薬確認",
        "information_sheet_provided": "情報提供文書有無",
        "source_system": "記録由来システム",
        "profile_updates": "頭書き差分",
        "additional_notes": "追加記載メモ",
    }

    def validate(self) -> None:
        """白紙のフォローアップ記録を拒否する。"""
        has_soap = self.soap.has_content
        has_additional = any(note.has_content for note in self.additional_notes)
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()


# --------------------------------------------------------------------------
# 処方医への服薬情報等提供（トレーシングレポート）
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class TracingReportResponse(ValueObject):
    """トレーシングレポートに対する処方医からの返答。"""

    responded_at: TracingReportTimestamp
    action_type: PrescriberActionType
    content: TracingReportResponseContent
    received_by: StaffId
    acknowledged_physician_name: PhysicianName | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "responded_at": "返答日時",
        "action_type": "対応区分",
        "content": "返答内容",
        "received_by": "受領者",
        "acknowledged_physician_name": "返答医師名",
    }


@dataclass(frozen=True, eq=False, kw_only=True)
class TracingReport(Entity[TracingReportId]):
    """処方医への服薬情報等提供（トレーシングレポート）記録。

    固有の識別子（TracingReportId）を持ち、処方医返答の受領・記録という
    状態遷移（ライフサイクル）を持つ集約内子エンティティ。
    """

    id: TracingReportId
    reporter_id: StaffId
    provided_at: TracingReportTimestamp
    medical_institution_name: MedicalInstitutionName
    physician_name: PhysicianName
    category: TracingReportCategory
    fee_category: TracingReportFeeCategory
    delivery_method: TracingReportDeliveryMethod
    content: TracingReportContent
    follow_up_id: FollowUpId | None = None
    response: TracingReportResponse | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "トレーシングレポートID",
        "reporter_id": "作成薬剤師",
        "provided_at": "提供日時",
        "medical_institution_name": "提供先医療機関",
        "physician_name": "提供先処方医",
        "category": "提供区分",
        "fee_category": "算定区分",
        "delivery_method": "提供手段",
        "content": "提供内容",
        "follow_up_id": "契機フォローアップID",
        "response": "医師返答",
    }

    @property
    def is_responded(self) -> bool:
        """医師からの返答が記録されているか。"""
        return self.response is not None

    def record_response(self, response: TracingReportResponse) -> Self:
        """処方医からの返答を記録する。

        Raises:
            TracingReportAlreadyRespondedError: 既に返答が記録されている場合。
            TracingReportResponseDateBeforeProvidedError: 返答日時が提供日時より前の場合。
        """
        if self.response is not None:
            raise TracingReportAlreadyRespondedError()
        if response.responded_at.value < self.provided_at.value:
            raise TracingReportResponseDateBeforeProvidedError()
        return replace(self, response=response)


# --------------------------------------------------------------------------
# 調剤録の記載事項（薬剤師法施行規則第16条第1項）
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class StatutoryPharmacistName(ValueObject):
    """調剤録へ記載する薬剤師1名の氏名。"""

    staff_id: StaffId
    names: PersonNames

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "staff_id": "スタッフ",
        "names": "氏名",
    }


@dataclass(frozen=True, kw_only=True)
class StatutoryInquiryRecord(ValueObject):
    """疑義照会1件のうち、調剤録の記載に必要な部分だけの写し。"""

    inquiry_number: InquiryNumber
    has_response: bool

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "inquiry_number": "照会連番",
        "has_response": "回答の有無",
    }


@dataclass(frozen=True, kw_only=True)
class StatutoryRecordSource(ValueObject):
    """薬歴コンテキストが自力で読めない記載事項の不変スナップショット。

    患者の同一性（``patient_id``）と患者の記載事項（氏名・生年月日）を**分離不能に**
    束ねる。分けると、そのスナップショットが本当にその患者のものかが呼び出し側の
    規約になり、別人の氏名を根拠に第一号が充足したと報告できてしまう。
    """

    patient_id: PatientId
    patient_names: PersonNames
    patient_birth_date: PatientBirthDate | None
    pharmacist_names: tuple[StatutoryPharmacistName, ...]
    prescription_id: PrescriptionId
    prescription_issued_date: PrescriptionIssuedDate
    prescriber_names: PersonName | None
    medical_institution_name: MedicalInstitutionName
    medical_institution_address: MedicalInstitutionAddressLine | None
    inquiries: tuple[StatutoryInquiryRecord, ...]

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "patient_id": "患者ID",
        "patient_names": "患者氏名",
        "patient_birth_date": "患者生年月日",
        "pharmacist_names": "薬剤師の氏名",
        "prescription_id": "処方箋ID",
        "prescription_issued_date": "処方箋交付年月日",
        "prescriber_names": "処方医氏名",
        "medical_institution_name": "医療機関名称",
        "medical_institution_address": "医療機関所在地",
        "inquiries": "疑義照会",
    }

    def find_pharmacist(self, staff_id: StaffId) -> StatutoryPharmacistName | None:
        """指定スタッフの氏名を返す。引けなければ ``None``。

        引けないことは取得の失敗ではなく、「氏名を記載できない」という判定材料。
        """
        for entry in self.pharmacist_names:
            if entry.staff_id == staff_id:
                return entry
        return None


@dataclass(frozen=True, kw_only=True)
class StatutoryItemAssessment(ValueObject):
    """記載事項1つの判定結果。"""

    item: StatutoryDispensingRecordItem
    state: StatutoryItemState

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "item": "記載事項",
        "state": "充足状態",
    }


@dataclass(frozen=True, kw_only=True)
class StatutoryRecordSufficiency(ValueObject):
    """薬歴が調剤録の代替になるかの判定結果。"""

    assessments: tuple[StatutoryItemAssessment, ...]
    blockers: tuple[StatutoryRecordBlocker, ...]

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "assessments": "記載事項の判定",
        "blockers": "代替を妨げる要因",
    }

    def validate(self) -> None:
        """全ての記載事項がちょうど1件ずつ判定されていることを検証する。

        判定表の網羅性はモジュール読み込み時に検査しているが、それは「判定関数が
        在るか」しか見ない。結果を組み立てる側で号を落とせば、充足していない薬歴が
        充足として返る。ここで構築を拒否すると、欠けた結果は存在しえなくなる。
        """
        self._ensure_each_item_assessed_once()

    def _ensure_each_item_assessed_once(self) -> None:
        """記載事項の重複と欠落を拒否する。"""
        assessed = [assessment.item for assessment in self.assessments]
        if len(assessed) != len(set(assessed)):
            raise StatutoryItemAssessedTwiceError()
        missing = [
            item for item in StatutoryDispensingRecordItem if item not in set(assessed)
        ]
        if missing:
            raise StatutoryItemNotAssessedError(
                item_labels=tuple(item.label for item in missing)
            )

    def state_of(self, item: StatutoryDispensingRecordItem) -> StatutoryItemState:
        """指定した記載事項の充足状態を返す。

        全ての記載事項がちょうど1件ずつ在ることは :meth:`validate` が保証するので、
        ここでは欠落を扱わない。
        """
        return next(
            assessment.state
            for assessment in self.assessments
            if assessment.item is item
        )

    @property
    def missing_items(self) -> tuple[StatutoryDispensingRecordItem, ...]:
        """記載が足りない事項。"""
        return tuple(
            assessment.item
            for assessment in self.assessments
            if assessment.state is StatutoryItemState.MISSING
        )

    @property
    def substitutes_dispensing_record(self) -> bool:
        """この薬歴が調剤録の代替になるか。

        記載事項がそろっていても、妨げる要因が1つでも残っていれば代替にならない。
        """
        return not self.blockers and not self.missing_items


@dataclass(frozen=True, kw_only=True)
class BillingAddition(ValueObject):
    """レセコンから連携された算定加算事実。

    点数計算や算定判定はレセコン側の排他的責務であるが、
    レセコンで算定された加算（特定薬剤管理指導加算、吸入薬指導加算等）の
    客観的事実を受容し、薬歴における指導根拠・確認事項の前提として保持する。
    """

    code: BillingAdditionCode
    name: BillingAdditionName
    points: int | None = None
    quantity: int | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code": "算定加算コード",
        "name": "算定加算名称",
        "points": "算定点数",
        "quantity": "算定数量",
    }
