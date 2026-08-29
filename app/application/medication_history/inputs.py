"""薬歴入力のDTO。

SOAP のラベル付き記述と、頭書きへの差分（Intent）を受け取る。
**由来（どの薬歴か・誰が・いつ）は入力に含めない。** 投影時に薬歴から埋まるので、
入力に持たせると薬歴と食い違う由来を書ける余地ができる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, kw_only=True)
class LabeledNoteInput:
    """法定カテゴリを付けた自由記述1件の入力。"""

    text: str
    category: str = "general"


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
class ProfileUpdateInput:
    """1回の服薬指導が頭書きへ加える差分の入力。"""

    new_allergies: tuple[AllergyIntentInput, ...] = field(default_factory=tuple)
    new_adverse_reactions: tuple[AdverseReactionIntentInput, ...] = field(
        default_factory=tuple
    )
    new_conditions: tuple[ConditionIntentInput, ...] = field(default_factory=tuple)
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
