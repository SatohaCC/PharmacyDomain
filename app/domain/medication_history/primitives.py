"""MedicationHistoryコンテキストの識別子・薬歴プリミティブ。

**電子処方箋管理サービス 記録条件仕様（調剤編）は本コンテキストの根拠ではない。**
同仕様には「薬歴」「服薬指導」「SOAP」の語が現れず、対応するレコードも別表も無い。
根拠は薬剤師法第25条の2・第28条、薬剤師法施行規則第16条、薬担規則第10条、および
保険調剤の理解のために（令和8年度）第2節 薬学管理料 通則(4) である。
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
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


class CategoryCatalogId(EntityUUID):
    """薬歴記載区分カタログ集約の一意識別子（UUIDv7）。"""

    identifier_name = "区分カタログID"


class FollowUpId(EntityUUID):
    """服薬期間中のフォローアップ記録を一意に識別するID（UUIDv7）。"""

    identifier_name = "フォローアップID"


class MajorCategoryCode(BaseNormalizedString):
    """大区分コード（英小文字推奨、例: soap, statutory）。"""


class MajorCategoryName(BaseNormalizedString):
    """大区分表示名（例: SOAP, 法令）。"""


class MediumCategoryCode(BaseNormalizedString):
    """中区分コード（例: s, o, a, p, handbook, residual_drug）。"""


class MediumCategoryName(BaseNormalizedString):
    """中区分表示名（例: S（主観的情報）, 残薬確認）。"""


# --------------------------------------------------------------------------
# 監査時刻
# --------------------------------------------------------------------------


class CounselingTimestamp(BaseAwareTimestamp):
    """服薬指導を行ったUTC時刻。頭書きへ畳み込む順序の基準になる。"""

    timestamp_name: ClassVar[str] = "服薬指導日時"


class MedicationHistoryImportTimestamp(BaseAwareTimestamp):
    """薬歴を外部システムから取り込んだUTC時刻。"""

    timestamp_name: ClassVar[str] = "薬歴取込時刻"


class AmendmentTimestamp(BaseAwareTimestamp):
    """確定済薬歴へ追記したUTC時刻。"""

    timestamp_name: ClassVar[str] = "追記日時"


class FinalizedTimestamp(BaseAwareTimestamp):
    """薬歴を確定した日時。"""

    timestamp_name: ClassVar[str] = "確定日時"


class MedicationHistoryReviewTimestamp(BaseAwareTimestamp):
    """薬剤師が確定内容を確認したUTC時刻。"""


class ExternalCorrectionTimestamp(BaseAwareTimestamp):
    """外部処方訂正を検知・記録したUTC日時。"""

    timestamp_name: ClassVar[str] = "外部訂正日時"


class FinalizationDelayReason(BaseNormalizedString):
    """薬歴確定の遅延理由（1〜200文字）。"""

    min_length: ClassVar[int] = 1
    max_length: ClassVar[int] = 200


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


class MedicationHistoryRecordKind(StrEnum):
    """初回薬歴か、過去薬歴を参照するフォローアップ薬歴か。"""

    INITIAL = "initial"
    FOLLOW_UP = "follow_up"


class MedicationHistoryReviewResult(StrEnum):
    """薬歴確定時に薬剤師が選択する確認結果。"""

    ASSESSMENT_AND_INSTRUCTION_RECORDED = "assessment_and_instruction_recorded"
    NO_ADDITIONAL_RECORDABLE_ITEMS = "no_additional_recordable_items"


class CounselingMethod(StrEnum):
    """服薬指導の実施方法。"""

    FACE_TO_FACE = "face_to_face"
    ONLINE = "online"
    TELEPHONE = "telephone"
    HOME_VISIT = "home_visit"
    OTC = "otc"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.FACE_TO_FACE: "対面",
            self.ONLINE: "オンライン",
            self.TELEPHONE: "電話",
            self.HOME_VISIT: "訪問",
            self.OTC: "OTC対応",
        }
        return labels[self]


class MedicationHistorySourceSystem(BaseFreeText):
    """薬歴またはフォローアップを起票した外部システム名。"""


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


class RetractionReason(BaseFreeText):
    """頭書き要素（アレルギー・副作用・疾患）を取り消す理由。"""


# --------------------------------------------------------------------------
# 調剤録の記載事項（薬剤師法第28条・施行規則第16条第1項）
# --------------------------------------------------------------------------


class StatutoryDispensingRecordItem(StrEnum):
    """薬剤師法施行規則第16条第1項が定める調剤録の記載事項。"""

    PATIENT_NAME_AND_AGE = "patient_name_and_age"
    MEDICINE_NAME_AND_AMOUNT = "medicine_name_and_amount"
    DISPENSED_AND_COUNSELED_DATE = "dispensed_and_counseled_date"
    DISPENSED_QUANTITY = "dispensed_quantity"
    PHARMACIST_NAMES = "pharmacist_names"
    COUNSELING_SUMMARY = "counseling_summary"
    PRESCRIPTION_ISSUED_DATE = "prescription_issued_date"
    PRESCRIBER_NAME = "prescriber_name"
    MEDICAL_INSTITUTION_LOCATION = "medical_institution_location"
    CHANGE_AND_INQUIRY_DETAIL = "change_and_inquiry_detail"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.PATIENT_NAME_AND_AGE: "患者の氏名及び年齢",
            self.MEDICINE_NAME_AND_AMOUNT: "薬名及び分量",
            self.DISPENSED_AND_COUNSELED_DATE: (
                "調剤並びに情報の提供及び指導を行った年月日"
            ),
            self.DISPENSED_QUANTITY: "調剤量",
            self.PHARMACIST_NAMES: ("調剤並びに情報の提供及び指導を行った薬剤師の氏名"),
            self.COUNSELING_SUMMARY: "情報の提供及び指導の内容の要点",
            self.PRESCRIPTION_ISSUED_DATE: "処方箋の発行年月日",
            self.PRESCRIBER_NAME: "処方箋を交付した医師等の氏名",
            self.MEDICAL_INSTITUTION_LOCATION: (
                "処方箋を交付した者の住所又は勤務する病院・診療所の名称及び所在地"
            ),
            self.CHANGE_AND_INQUIRY_DETAIL: "変更調剤の内容及び疑義照会の回答内容",
        }
        return labels[self]

    @property
    def article_clause(self) -> str:
        """記載事項の根拠となる条文の位置。

        個別指導では「その記載はどの号か」を示すことになるので、号まで持つ。
        応答本文に単独で現れても法令が特定できるよう、法令名から書く。
        """
        clauses = {
            self.PATIENT_NAME_AND_AGE: "第16条第1項第一号",
            self.MEDICINE_NAME_AND_AMOUNT: "第16条第1項第二号",
            self.DISPENSED_AND_COUNSELED_DATE: "第16条第1項第三号",
            self.DISPENSED_QUANTITY: "第16条第1項第四号",
            self.PHARMACIST_NAMES: "第16条第1項第五号",
            self.COUNSELING_SUMMARY: "第16条第1項第六号",
            self.PRESCRIPTION_ISSUED_DATE: "第16条第1項第七号",
            self.PRESCRIBER_NAME: "第16条第1項第八号",
            self.MEDICAL_INSTITUTION_LOCATION: "第16条第1項第九号",
            self.CHANGE_AND_INQUIRY_DETAIL: "第16条第1項第十号（第15条第一号・第二号）",
        }
        return f"薬剤師法施行規則{clauses[self]}"


class StatutoryItemState(StrEnum):
    """記載事項1つの充足状態。

    ``NOT_REQUIRED`` を返してよいのは、源データが「その事由が発生していない」ことを
    **積極的に示している**ときだけ。判定できないことを「該当しない」に倒すと、
    記載の漏れが充足として報告される。
    """

    RECORDED = "recorded"
    MISSING = "missing"
    NOT_REQUIRED = "not_required"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.RECORDED: "記載済",
            self.MISSING: "未記載",
            self.NOT_REQUIRED: "該当なし",
        }
        return labels[self]


class StatutoryRecordBlocker(StrEnum):
    """記載事項とは別軸で、調剤録の代替を妨げる要因。

    記載事項の表へ混ぜない。混ぜると号と項目の対応が崩れ、「第何号が足りないのか」
    という問いに答えられなくなる。
    """

    MEDICATION_HISTORY_NOT_FINALIZED = "medication_history_not_finalized"
    DISPENSING_NOT_COMPLETED = "dispensing_not_completed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.MEDICATION_HISTORY_NOT_FINALIZED: "薬歴が未確定",
            self.DISPENSING_NOT_COMPLETED: "調剤が未完了",
        }
        return labels[self]


# --------------------------------------------------------------------------
# 処方医への服薬情報等提供（トレーシングレポート）
# --------------------------------------------------------------------------


class TracingReportId(EntityUUID):
    """トレーシングレポートの一意識別子。"""

    identifier_name: ClassVar[str] = "トレーシングレポートID"


class TracingReportTimestamp(BaseAwareTimestamp):
    """トレーシングレポートの提供・返答日時。"""

    timestamp_name: ClassVar[str] = "トレーシングレポート日時"


class TracingReportCategory(StrEnum):
    """トレーシングレポートの提供区分。"""

    RESIDUAL_DRUG = "residual_drug"
    ADVERSE_REACTION = "adverse_reaction"
    ADHERENCE = "adherence"
    PRESCRIPTION_PROPOSAL = "prescription_proposal"
    PATIENT_CONSULTATION = "patient_consultation"
    OTHER = "other"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.RESIDUAL_DRUG: "残薬調整",
            self.ADVERSE_REACTION: "副作用疑い・モニタリング",
            self.ADHERENCE: "服薬状況・アドヒアランス",
            self.PRESCRIPTION_PROPOSAL: "処方提案・ポリファーマシー",
            self.PATIENT_CONSULTATION: "患者相談・生活状況",
            self.OTHER: "その他",
        }
        return labels[self]


class TracingReportFeeCategory(StrEnum):
    """調剤報酬 服薬情報等提供料の区分。"""

    FEE_1 = "fee_1"
    FEE_2 = "fee_2"
    FEE_3 = "fee_3"
    NONE = "none"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.FEE_1: "服薬情報等提供料1",
            self.FEE_2: "服薬情報等提供料2",
            self.FEE_3: "服薬情報等提供料3",
            self.NONE: "算定なし",
        }
        return labels[self]


class TracingReportDeliveryMethod(StrEnum):
    """トレーシングレポートの提供手段。"""

    FAX = "fax"
    MAIL = "mail"
    ELECTRONIC = "electronic"
    HAND_DELIVERY = "hand_delivery"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.FAX: "FAX",
            self.MAIL: "郵送",
            self.ELECTRONIC: "電子",
            self.HAND_DELIVERY: "手渡し",
        }
        return labels[self]


class PrescriberActionType(StrEnum):
    """トレーシングレポートに対する処方医の対応区分。"""

    AGREED_REFLECT_NEXT = "agreed_reflect_next"
    MAINTAIN_CURRENT = "maintain_current"
    EXAMINATION_REQUIRED = "examination_required"
    ACKNOWLEDGED = "acknowledged"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.AGREED_REFLECT_NEXT: "次回処方に反映・変更",
            self.MAINTAIN_CURRENT: "現状維持・継続観察",
            self.EXAMINATION_REQUIRED: "追加検査・受診指示",
            self.ACKNOWLEDGED: "確認・了解",
        }
        return labels[self]


class PhysicianName(BaseNormalizedString):
    """処方医氏名。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("処方医氏名は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError("処方医氏名は100文字以内で指定してください。")


class TracingReportContent(BaseFreeText):
    """トレーシングレポートの提供内容。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("提供内容は空にできません。")
        if len(self.value) > 2000:
            raise DomainValidationError("提供内容は2000文字以内で指定してください。")


class TracingReportResponseContent(BaseFreeText):
    """トレーシングレポートに対する医師の返答内容。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("返答内容は空にできません。")
        if len(self.value) > 2000:
            raise DomainValidationError("返答内容は2000文字以内で指定してください。")


class BillingAdditionCode(BaseNormalizedString):
    """算定加算コード（レセ電コード等の客観的符号）。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("算定加算コードは空にできません。")
        if len(self.value) > 30:
            raise DomainValidationError(
                "算定加算コードは30文字以内で指定してください。"
            )


class BillingAdditionName(BaseNormalizedString):
    """算定加算名称（例: 特定薬剤管理指導加算２）。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("算定加算名称は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError("算定加算名称は100文字以内で指定してください。")
