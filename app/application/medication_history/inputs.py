"""薬歴入力のDTO。

SOAP のラベル付き記述と、頭書きへの差分（Intent）を受け取る。
**由来（どの薬歴か・誰が・いつ）は入力に含めない。** 投影時に薬歴から埋まるので、
入力に持たせると薬歴と食い違う由来を書ける余地ができる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True, kw_only=True)
class LabeledNoteInput:
    """法定カテゴリを付けた自由記述1件の入力。"""

    text: str
    category: str = "general"


@dataclass(frozen=True, kw_only=True)
class CategorizedNoteInput:
    """大区分・中区分に紐づく記載メモ1件の入力。"""

    major_category_code: str
    medium_category_code: str
    text: str
    category: str = "general"


@dataclass(frozen=True, kw_only=True)
class MajorCategoryInput:
    """大区分定義の入力。"""

    code: str
    name: str
    display_order: int
    is_enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class MediumCategoryInput:
    """中区分定義の入力。"""

    code: str
    major_category_code: str
    name: str
    display_order: int
    is_required: bool = False
    is_enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class UpdateCategoryCatalogCommand:
    """法人別薬歴記載区分カタログの更新入力。"""

    corporate_id: str
    major_categories: tuple[MajorCategoryInput, ...] = ()
    medium_categories: tuple[MediumCategoryInput, ...] = ()


@dataclass(frozen=True, kw_only=True)
class SoapInput:
    """SOAP各セクションの入力。"""

    subjective: tuple[LabeledNoteInput, ...] = field(default_factory=tuple)
    objective: tuple[LabeledNoteInput, ...] = field(default_factory=tuple)
    assessment: tuple[LabeledNoteInput, ...] = field(default_factory=tuple)
    plan: tuple[LabeledNoteInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class ResidualDrugInput:
    """残薬状況の入力（法定記載事項ウ（ホ））。"""

    has_residual_drugs: bool
    quantity: int | None = None
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class HandbookStatusInput:
    """お薬手帳の活用状況の入力（法定記載事項ウ（ト））。"""

    presented: bool
    not_presented_reason: str | None = None
    guidance_provided: bool | None = None
    multiple_handbooks_not_consolidated_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class AllergyIntentInput:
    """聞き取ったアレルギー歴の入力。"""

    allergen: str
    reaction: str
    severity: str


@dataclass(frozen=True, kw_only=True)
class AdverseReactionIntentInput:
    """聞き取った副作用歴の入力。"""

    medicine_name: str
    symptom: str
    occurred_on: date | None = None


@dataclass(frozen=True, kw_only=True)
class ConditionIntentInput:
    """聞き取った疾患の入力。"""

    condition_name: str
    condition_status: str
    is_contraindication_target: bool = False


@dataclass(frozen=True, kw_only=True)
class ConcurrentMedicationIntentInput:
    """聞き取った併用薬の開始の入力。"""

    medicine_name: str
    category: str
    started_on: date
    prescriber_institution: str | None = None


@dataclass(frozen=True, kw_only=True)
class StopConcurrentMedicationIntentInput:
    """聞き取った併用薬の終了の入力。"""

    medicine_name: str
    ended_on: date


@dataclass(frozen=True, kw_only=True)
class RetractAllergyIntentInput:
    """取り消すアレルギー歴の入力。"""

    allergen: str
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class RetractAdverseReactionIntentInput:
    """取り消す副作用歴の入力。"""

    medicine_name: str
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateConditionStatusIntentInput:
    """更新する疾患状態の入力。"""

    condition_name: str
    new_status: str
    is_contraindication_target: bool | None = None


@dataclass(frozen=True, kw_only=True)
class RetractConditionIntentInput:
    """取り消す疾患の入力。"""

    condition_name: str
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileUpdateInput:
    """1回の服薬指導が頭書きへ加える差分の入力。"""

    new_allergies: tuple[AllergyIntentInput, ...] = field(default_factory=tuple)
    retracted_allergies: tuple[RetractAllergyIntentInput, ...] = field(
        default_factory=tuple
    )
    new_adverse_reactions: tuple[AdverseReactionIntentInput, ...] = field(
        default_factory=tuple
    )
    retracted_adverse_reactions: tuple[RetractAdverseReactionIntentInput, ...] = field(
        default_factory=tuple
    )
    new_conditions: tuple[ConditionIntentInput, ...] = field(default_factory=tuple)
    updated_conditions: tuple[UpdateConditionStatusIntentInput, ...] = field(
        default_factory=tuple
    )
    retracted_conditions: tuple[RetractConditionIntentInput, ...] = field(
        default_factory=tuple
    )
    new_concurrent_medications: tuple[ConcurrentMedicationIntentInput, ...] = field(
        default_factory=tuple
    )
    stopped_concurrent_medications: tuple[StopConcurrentMedicationIntentInput, ...] = (
        field(default_factory=tuple)
    )
    lifestyle_note: str | None = None
    generic_preference: str | None = None
    family_pharmacist_id: str | None = None
    family_pharmacist_agreed_on: date | None = None


@dataclass(frozen=True, kw_only=True)
class AddFollowUpCommand:
    """服薬期間中のフォローアップ追加コマンド。"""

    corporate_id: str
    record_id: str
    counselor_id: str
    followed_up_at: datetime
    method: str
    soap: SoapInput = field(default_factory=SoapInput)
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool = False
    profile_updates: ProfileUpdateInput | None = None
    additional_notes: tuple[CategorizedNoteInput, ...] = ()


@dataclass(frozen=True, kw_only=True)
class RecordTracingReportCommand:
    """処方医への服薬情報等提供（トレーシングレポート）記録コマンド。"""

    corporate_id: str
    record_id: str
    reporter_id: str
    provided_at: datetime
    medical_institution_name: str
    physician_name: str
    category: str
    fee_category: str
    delivery_method: str
    content: str
    follow_up_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class RecordTracingReportResponseCommand:
    """トレーシングレポートに対する処方医返答の記録コマンド。"""

    corporate_id: str
    record_id: str
    tracing_report_id: str
    responded_at: datetime
    content: str
    action_type: str
    received_by: str
    acknowledged_physician_name: str | None = None
