"""MedicationHistoryコンテキストの識別子・薬歴プリミティブ。

**電子処方箋管理サービス 記録条件仕様（調剤編）は本コンテキストの根拠ではない。**
同仕様には「薬歴」「服薬指導」「SOAP」の語が現れず、対応するレコードも別表も無い。
根拠は薬剤師法第25条の2・第28条、薬剤師法施行規則第16条、薬担規則第10条、および
保険調剤の理解のために（令和8年度）第2節 薬学管理料 通則(4) である。
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.primitives.primitives import (
    BaseAwareTimestamp,
    BaseFreeText,
    BaseNormalizedString,
    BasePositiveInt,
    EntityUUID,
)

# --------------------------------------------------------------------------
# 識別子
# --------------------------------------------------------------------------


class MedicationHistoryRecordId(EntityUUID):
    """薬歴指導記録集約の一意識別子（UUIDv7）。"""

    identifier_name = "薬歴ID"


class PatientMedicalProfileId(EntityUUID):
    """患者医療プロファイル（頭書き）集約の一意識別子（UUIDv7）。

    ``PatientId`` を流用しない。他集約のIDを自分のIDにすると、患者の統合・削除が
    起きたときにプロファイルの同一性をどう扱うかが決まらなくなる。患者との
    1:1関係は ``patient_id`` の一意制約（Repository契約）で表す。
    """

    identifier_name = "頭書きID"


# --------------------------------------------------------------------------
# 監査時刻
# --------------------------------------------------------------------------


class CounselingTimestamp(BaseAwareTimestamp):
    """服薬指導を行ったUTC時刻。頭書きへ畳み込む順序の基準になる。"""

    timestamp_name: ClassVar[str] = "服薬指導日時"


class AmendmentTimestamp(BaseAwareTimestamp):
    """確定済薬歴へ追記したUTC時刻。"""

    timestamp_name: ClassVar[str] = "追記日時"


# --------------------------------------------------------------------------
# 薬歴の状態・指導方法
# --------------------------------------------------------------------------


class MedicationHistoryStatus(StrEnum):
    """薬歴の状態。"""

    DRAFT = "draft"
    FINALIZED = "finalized"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.DRAFT: "下書き", self.FINALIZED: "確定済"}
        return labels[self]

    @property
    def is_finalized(self) -> bool:
        """確定済か。"""
        return self is MedicationHistoryStatus.FINALIZED


class CounselingMethod(StrEnum):
    """服薬指導の実施方法。"""

    FACE_TO_FACE = "face_to_face"
    ONLINE = "online"
    TELEPHONE = "telephone"
    HOME_VISIT = "home_visit"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.FACE_TO_FACE: "対面",
            self.ONLINE: "オンライン",
            self.TELEPHONE: "電話",
            self.HOME_VISIT: "訪問",
        }
        return labels[self]


# --------------------------------------------------------------------------
# 法定カテゴリ付きテキスト
# --------------------------------------------------------------------------


class StatutoryCategory(StrEnum):
    """SOAPの自由記述に付与する法定記載事項のラベル。

    出典: 保険調剤の理解のために（令和8年度）第2節 薬学管理料 通則(4)。
    個別指導で「体調変化の確認はどこか」と問われたときに、長文を読まずに
    示せるようにするためのもの。
    """

    PATIENT_CONDITION_CHANGE = "patient_condition_change"
    MEDICATION_ADHERENCE = "medication_adherence"
    RESIDUAL_DRUG = "residual_drug"
    CONCURRENT_MEDICATION = "concurrent_medication"
    LIFESTYLE_AND_DIET = "lifestyle_and_diet"
    HANDBOOK_GUIDANCE = "handbook_guidance"
    GENERIC_PREFERENCE = "generic_preference"
    PATIENT_INQUIRY = "patient_inquiry"
    FUTURE_PLAN_CAUTION = "future_plan_caution"
    GENERAL = "general"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.PATIENT_CONDITION_CHANGE: "体調変化・副作用確認",
            self.MEDICATION_ADHERENCE: "服薬状況・遵守",
            self.RESIDUAL_DRUG: "残薬状況・理由",
            self.CONCURRENT_MEDICATION: "併用薬・他院処方・OTC",
            self.LIFESTYLE_AND_DIET: "生活状況・飲食物相互作用",
            self.HANDBOOK_GUIDANCE: "お薬手帳の活用・指導",
            self.GENERIC_PREFERENCE: "後発医薬品使用意向",
            self.PATIENT_INQUIRY: "患者・家族相談事項",
            self.FUTURE_PLAN_CAUTION: "今後指導留意点・フォロー",
            self.GENERAL: "一般・指定なし",
        }
        return labels[self]


class CounselingNote(BaseFreeText):
    """SOAPの自由記述1件分。

    通則(5) は「定型文を用いて画一的に記載するのではなく」と定めており、
    構造化するのはラベルまでで、本文は自由記述のまま持つ。
    """


# --------------------------------------------------------------------------
# 残薬・お薬手帳
# --------------------------------------------------------------------------


class ResidualDrugQuantity(BasePositiveInt):
    """残薬の数量（日数または回数）。"""

    quantity_name: ClassVar[str] = "残薬数量"


class ResidualDrugReason(BaseFreeText):
    """残薬が生じた理由。"""


class HandbookNotPresentedReason(BaseFreeText):
    """お薬手帳を活用しなかった理由（持参忘れ、手帳不要の意向等）。"""


class HandbookConsolidationReason(BaseFreeText):
    """複数の手帳を1冊にまとめなかった理由。"""


# --------------------------------------------------------------------------
# 頭書きの要素
# --------------------------------------------------------------------------


class AllergenName(BaseNormalizedString):
    """アレルゲン名（ペニシリン系、卵 等）。"""


class AllergyReaction(BaseNormalizedString):
    """アレルギー症状（皮疹、アナフィラキシー 等）。"""


class AllergySeverity(StrEnum):
    """アレルギーの重篤度。"""

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.MILD: "軽度", self.MODERATE: "中等度", self.SEVERE: "重度"}
        return labels[self]


class AdverseReactionSymptom(BaseNormalizedString):
    """副作用症状（胃痛、発熱、浮腫 等）。"""


class ConditionName(BaseNormalizedString):
    """疾患名（緑内障、前立腺肥大、喘息 等）。"""


class ConditionStatus(StrEnum):
    """疾患の状態。"""

    ONGOING = "ongoing"
    CONTROLLED = "controlled"
    RESOLVED = "resolved"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.ONGOING: "加療中",
            self.CONTROLLED: "コントロール良好",
            self.RESOLVED: "既往（治癒）",
        }
        return labels[self]


class ConcurrentCategory(StrEnum):
    """併用薬の分類。

    法定記載事項ウ（ハ）「併用薬（要指導医薬品、一般用医薬品、医薬部外品及び
    健康食品を含む）等の状況」の列挙に対応する。飲食物は薬品ではないため
    ここには含めず、生活像側で扱う。
    """

    PRESCRIPTION = "prescription"
    GUIDANCE_REQUIRED = "guidance_required"
    OTC = "otc"
    QUASI_DRUG = "quasi_drug"
    HEALTH_FOOD = "health_food"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.PRESCRIPTION: "他院・他科の処方薬",
            self.GUIDANCE_REQUIRED: "要指導医薬品",
            self.OTC: "一般用医薬品",
            self.QUASI_DRUG: "医薬部外品",
            self.HEALTH_FOOD: "健康食品",
        }
        return labels[self]


class GenericPreferenceType(StrEnum):
    """後発医薬品の使用に関する患者の意向（法定記載事項ウ（イ））。"""

    ACCEPTS = "accepts"
    REFUSES = "refuses"
    UNDECIDED = "undecided"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.ACCEPTS: "後発医薬品を希望する",
            self.REFUSES: "後発医薬品を希望しない",
            self.UNDECIDED: "意向未確認・保留",
        }
        return labels[self]


class LifestyleNote(BaseFreeText):
    """生活像の記述。

    法定記載事項ウ（イ）「薬学的管理に必要な患者の生活像」と、
    ウ（ハ）後段「服用薬と相互作用が認められる飲食物の摂取状況」を扱う。
    """


class AmendmentReason(BaseFreeText):
    """確定済薬歴へ追記した理由。"""
