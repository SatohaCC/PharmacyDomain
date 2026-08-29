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
from dataclasses import dataclass
from datetime import date
from typing import ClassVar, Self

from app.base.domain.medicine import MedicineName
from app.base.domain.value_object import ValueObject
from app.domain.medication_history.exceptions import (
    ConcurrentMedicationPeriodInvertedError,
    HandbookGuidanceRequiredError,
    HandbookReasonNotAllowedError,
    ResidualDrugDetailNotAllowedError,
    ResidualDrugDetailRequiredError,
)
from app.domain.medication_history.primitives import (
    AdverseReactionSymptom,
    AllergenName,
    AllergyReaction,
    AllergySeverity,
    AmendmentReason,
    AmendmentTimestamp,
    ConcurrentCategory,
    ConditionName,
    ConditionStatus,
    CounselingNote,
    GenericPreferenceType,
    HandbookConsolidationReason,
    HandbookNotPresentedReason,
    LifestyleNote,
    MedicationHistoryRecordId,
    ResidualDrugQuantity,
    ResidualDrugReason,
    StatutoryCategory,
)
from app.domain.prescription.primitives import MedicalInstitutionName
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
    new_adverse_reactions: tuple[NewAdverseReactionIntent, ...] = ()
    new_conditions: tuple[NewConditionIntent, ...] = ()
    new_concurrent_medications: tuple[NewConcurrentMedicationIntent, ...] = ()
    stopped_concurrent_medications: tuple[StopConcurrentMedicationIntent, ...] = ()
    lifestyle_update: LifestyleUpdateIntent | None = None
    generic_preference_update: GenericPreferenceIntent | None = None
    family_pharmacist_update: FamilyPharmacistIntent | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "new_allergies": "追加するアレルギー歴",
        "new_adverse_reactions": "追加する副作用歴",
        "new_conditions": "追加する疾患",
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
            or self.new_adverse_reactions
            or self.new_conditions
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
