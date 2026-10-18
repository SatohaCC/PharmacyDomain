"""dispensingの単一値と列挙・検証規則。"""

from __future__ import annotations

from enum import Enum, StrEnum, auto
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseAwareTimestamp,
    BaseDate,
    BaseFreeText,
    BaseNormalizedString,
    BasePositiveDecimal,
    BasePositiveInt,
)

# --------------------------------------------------------------------------
# 識別子
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 調剤回数と分割理由
# --------------------------------------------------------------------------


class DispensingIteration(BasePositiveInt):
    """1枚の処方箋に対する何回目の調剤かを表す回数。

    **上限はこの型では課さない。** 上限は分割理由ごとに異なり
    （注10は2回・注11は3回・注9は定めなし）、リフィルでは処方箋側の
    総使用回数に従う。型の不変条件にすると、上限の無い注9を表現できない。
    範囲の判定は :class:`DispensingSplitReason` と Domain Service が担う。
    """

    quantity_name: ClassVar[str] = "調剤回数"


class TotalSplitCount(BasePositiveInt):
    """分割調剤における合計分割回数（全何回分割か）。

    分割調剤である以上、2分割以上（2以上の整数）である必要がある。
    注9（長期保存困難等）など回数上限の定めがない分割調剤も存在するため、
    この型自体には特定の上限値（3回等）は課さない。
    """

    quantity_name: ClassVar[str] = "合計分割回数"

    def validate(self) -> None:
        super().validate()
        if self.value < 2:
            raise DomainValidationError("合計分割回数は2回以上で指定してください。")


class DispensingSplitReason(StrEnum):
    """分割調剤の理由（調剤基本料の注9・注10・注11）。

    出典: 保険調剤の理解のために（令和8年度）。

    **リフィル処方箋はここに含めない。** リフィルは処方箋側の指示
    （``Prescription.management_info.refill``）であり、分割調剤とは回数の
    根拠も算定方法も異なる。同じ列挙に混ぜると、どちらの上限を適用するかが
    呼び出し側の判断になる。
    """

    LONG_TERM_STORAGE = "long_term_storage"
    GENERIC_TRIAL = "generic_trial"
    PRESCRIBER_INSTRUCTED = "prescriber_instructed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.LONG_TERM_STORAGE: "長期保存の困難性等による分割調剤",
            self.GENERIC_TRIAL: "後発医薬品の試用のための分割調剤",
            self.PRESCRIBER_INSTRUCTED: "医師の分割指示による分割調剤",
        }
        return labels[self]

    @property
    def note_number(self) -> str:
        """調剤基本料における注番号。"""
        numbers = {
            self.LONG_TERM_STORAGE: "9",
            self.GENERIC_TRIAL: "10",
            self.PRESCRIBER_INSTRUCTED: "11",
        }
        return numbers[self]


class DispensedDate(BaseDate):
    """調剤を行った年月日（業務日）。"""


class NextDispensingDate(BaseDate):
    """次回調剤予定日。

    出典: 調剤編 ``リフィル処方箋情報レコード(521)``。調剤終了区分に ``2``
    （継続）を記録した場合に記録する。**薬局が記録する値であり、投薬期間から
    計算した値ではない。** リフィル2回目以降の前後7日判定はこの値を基準にする。
    """


# --------------------------------------------------------------------------
# 監査時刻
# --------------------------------------------------------------------------


class DispensingTimestamp(BaseAwareTimestamp):
    """調剤セッションを開始したUTC時刻。"""

    timestamp_name: ClassVar[str] = "調剤開始日時"


class AuditTimestamp(BaseAwareTimestamp):
    """処方鑑査を行ったUTC時刻。"""

    timestamp_name: ClassVar[str] = "処方鑑査日時"


class VerificationTimestamp(BaseAwareTimestamp):
    """最終鑑査（調剤鑑査）を行ったUTC時刻。"""

    timestamp_name: ClassVar[str] = "最終鑑査日時"


class DispensingCompletionTimestamp(BaseAwareTimestamp):
    """調剤録を完了として確定したUTC時刻。"""

    timestamp_name: ClassVar[str] = "調剤完了日時"


# --------------------------------------------------------------------------
# 変更調剤の3軸
# --------------------------------------------------------------------------


class SubstitutionCategory(StrEnum):
    """軸1: 代替調剤の種別。処方薬品**そのものを置き換えた**場合だけ記録する。

    **「処方どおり」を表す値は持たない。** 処方どおりなら
    ``DispensedMedicine.substitution is None`` である。両方あると同じ事実に
    2通りの表現ができ、集計時にどちらを数えるかが規約になる。
    """

    GENERIC_SUBSTITUTION = "generic_substitution"
    STRENGTH_CHANGE = "strength_change"
    DOSAGE_FORM_CHANGE = "dosage_form_change"
    INQUIRY_MODIFIED = "inquiry_modified"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.GENERIC_SUBSTITUTION: "後発医薬品への変更調剤",
            self.STRENGTH_CHANGE: "規格変更調剤",
            self.DOSAGE_FORM_CHANGE: "剤形変更調剤",
            self.INQUIRY_MODIFIED: "疑義照会に基づく処方変更調剤",
        }
        return labels[self]


class QuantityAdjustmentReason(StrEnum):
    """軸2: 数量調整の理由。

    保険調剤の理解のために（令和8年度）の定義: 「処方箋に記載された医薬品に
    ついて、用法及び用量の変更は行わずに投与日数等を減らす調剤（減数調剤）」。
    """

    RESIDUAL_DRUG = "residual_drug"
    INQUIRY_AGREED = "inquiry_agreed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.RESIDUAL_DRUG: "残薬確認に基づく減数調剤",
            self.INQUIRY_AGREED: "疑義照会の合意による数量変更",
        }
        return labels[self]


class PreparationMethod(StrEnum):
    """軸3: 調製方法。薬品自体は処方どおりで、調製の仕方が加わるもの。

    複数同時に成立する（一包化しつつ粉砕する等）。**加算の排他ルールは
    ここに持たない。** 算定可否は請求算定側の責務であり、ここで
    排他にすると実施した事実を記録できなくなる。
    """

    UNIT_DOSE_PACKAGED = "unit_dose_packaged"
    COMPOUNDED = "compounded"
    MEASURED_MIXING = "measured_mixing"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.UNIT_DOSE_PACKAGED: "一包化",
            self.COMPOUNDED: "自家製剤",
            self.MEASURED_MIXING: "計量混合",
        }
        return labels[self]


class SubstitutionReason(BaseFreeText):
    """代替調剤を行った理由の自由記述。"""


# --------------------------------------------------------------------------
# 鑑査
# --------------------------------------------------------------------------


class VerificationResult(StrEnum):
    """最終鑑査（調剤鑑査）の結果。"""

    PASSED = "passed"
    FAILED = "failed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.PASSED: "合格", self.FAILED: "不合格"}
        return labels[self]

    @property
    def is_passed(self) -> bool:
        """合格か。"""
        return self is VerificationResult.PASSED


class AuditNotes(BaseFreeText):
    """処方鑑査の所見。"""


class VerificationNotes(BaseFreeText):
    """最終鑑査の所見。"""


class DispensingCancellationReason(BaseFreeText):
    """調剤中止の理由。"""


# --------------------------------------------------------------------------
# 状態
# --------------------------------------------------------------------------


class DispensingProcessStatus(StrEnum):
    """調剤セッションの状態。"""

    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.IN_PROGRESS: "調剤調製中",
            self.VERIFIED: "最終鑑査済（交付待ち）",
            self.COMPLETED: "交付済",
            self.CANCELLED: "調剤中止",
        }
        return labels[self]

    @property
    def is_terminal(self) -> bool:
        """これ以上状態が動かない終端か。"""
        return self in {
            DispensingProcessStatus.COMPLETED,
            DispensingProcessStatus.CANCELLED,
        }


class DispensingCompletionType(StrEnum):
    """調剤終了区分。

    出典: 調剤編 ``リフィル処方箋情報レコード(521)``。

    ``COMPLETED`` は「調剤回数が総使用回数に達した場合**または達していないが
    次回以降の調剤が不要となった場合**」であり、回数だけでは決まらない。
    ``Prescription`` を調剤済へ遷移させる契機はこの区分であって、
    ``iteration == total_refill_count`` ではない。
    """

    COMPLETED = "completed"
    CONTINUES = "continues"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {self.COMPLETED: "1", self.CONTINUES: "2"}
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.COMPLETED: "調剤終了", self.CONTINUES: "調剤継続"}
        return labels[self]

    @property
    def requires_next_date(self) -> bool:
        """次回調剤予定日の記録が必要か。"""
        return self is DispensingCompletionType.CONTINUES


class MedicineCodeType(StrEnum):
    """薬品コードの体系。

    JAHISの紙処方箋では6体系を使う一方、電子処方箋では使用可能な体系が
    異なる。電子処方箋との組み合わせ判定は、このコード体系ではなく
    ``Prescription`` が受領元形式と一緒に行う。
    """

    NONE = "none"
    RECEIPT = "receipt"
    MHLW = "mhlw"
    YJ = "yj"
    HOT = "hot"
    GENERIC = "generic"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.NONE: "1",
            self.RECEIPT: "2",
            self.MHLW: "3",
            self.YJ: "4",
            self.HOT: "6",
            self.GENERIC: "7",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NONE: "コードなし",
            self.RECEIPT: "レセプト電算処理システム用コード",
            self.MHLW: "厚生省コード",
            self.YJ: "YJコード",
            self.HOT: "HOTコード",
            self.GENERIC: "一般名コード",
        }
        return labels[self]


class MedicineCode(BaseNormalizedString):
    """薬品コード。

    桁数はコード体系ごとに異なる（レセプト電算・YJ・HOT・一般名）。電子処方箋の
    処方編・調剤編も薬品レコードを「薬品コード X 13 可変」と定めているため、
    ここでは固定桁数を課さない。コード体系ごとの妥当性は取り込み元で検証する。
    """


class MedicineName(BaseNormalizedString):
    """薬品名称。

    医薬品マスタの表示名だけでなく、未収載薬・OTC・健康食品の名称も表す。
    この値を持つことは医薬品マスタ行の存在を意味しない。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 180:
            raise DomainValidationError("薬品名称は180文字以内で指定してください。")


class MedicineUnit(BaseNormalizedString):
    """薬品の単位名（錠、g、mL、包 等）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 20:
            raise DomainValidationError("単位名は20文字以内で指定してください。")


class DosageFormCategory(StrEnum):
    """処方箋に記載する剤形区分。

    出典は電子処方箋（処方編）別表13およびJAHISレコードNo.101備考欄。
    """

    INTERNAL = "internal"
    PRN = "prn"
    TOPICAL = "topical"
    INTERNAL_DROPS = "internal_drops"
    INJECTION = "injection"
    SUPPLY = "supply"
    OTHER = "other"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.INTERNAL: "1",
            self.PRN: "2",
            self.TOPICAL: "3",
            self.INTERNAL_DROPS: "4",
            self.INJECTION: "5",
            self.SUPPLY: "6",
            self.OTHER: "9",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.INTERNAL: "内服",
            self.PRN: "頓服",
            self.TOPICAL: "外用",
            self.INTERNAL_DROPS: "内服滴剤",
            self.INJECTION: "注射",
            self.SUPPLY: "医療材料",
            self.OTHER: "不明",
        }
        return labels[self]

    @property
    def quantity_meaning(self) -> str:
        """調剤数量が何を表すか。"""
        if self is DosageFormCategory.INTERNAL:
            return "投与日数"
        if self is DosageFormCategory.PRN:
            return "投与回数"
        return "投与日数または回数"


class DosageAmount(BasePositiveDecimal):
    """処方箋に記載する薬品の分量。

    内服は1日量、頓服は1回量、外用・材料は処方総量を表す（剤形区分で決まる）。
    整数部6桁・小数部5桁で、``float`` は受け付けない。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "分量"


class DispensingQuantity(BasePositiveInt):
    """剤に記載する調剤数量。

    剤形区分により投与日数、投与回数、その他の日数または回数を表す。
    薬品の用量に総量を記録する場合は1を記録する。
    """

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("調剤数量は999以内で指定してください。")


class RpNumber(BasePositiveInt):
    """処方箋内の剤番号（RP番号）。1から連番。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("RP番号は999以内で指定してください。")


class MedicineLineNumber(BasePositiveInt):
    """RP内の薬品連番。1から連番。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("RP内連番は999以内で指定してください。")


class PrescriptionStatus(StrEnum):
    """処方箋原本のライフサイクル状態。

    「疑義照会中」は状態として持たない。未回答の照会があるかは
    ``Prescription.has_open_inquiry`` から導出する。状態にすると
    (1) 照会解決後にどの状態へ戻すかが ``status`` だけでは決まらず、
    (2) 「照会中なのに未回答が0件」という矛盾が構築可能になる。
    """

    RECEIVED = "received"
    READY_FOR_DISPENSING = "ready_for_dispensing"
    DISPENSED = "dispensed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.RECEIVED: "受付済",
            self.READY_FOR_DISPENSING: "調剤可能",
            self.DISPENSED: "調剤済",
            self.CANCELLED: "取消・無効",
        }
        return labels[self]

    @property
    def is_terminal(self) -> bool:
        """以降の状態変更を受け付けない終端状態か。"""
        return self in (PrescriptionStatus.DISPENSED, PrescriptionStatus.CANCELLED)


class GenericSubstitutionRestrictionType(StrEnum):
    """薬品補足区分のうち**変更制限**にあたる値。

    出典: 処方編 別表16 / JAHIS レコードNo.281。
    3〜6は医師が変更を禁じる指示（保険医の署名・理由が必要）、
    8は患者自身が長期収載品を希望する選定療養指示。いずれも調剤時の
    代替可否を決めるため同じ型に束ねる。
    """

    NO_GENERIC = "no_generic"
    NO_FORM_CHANGE = "no_form_change"
    NO_STRENGTH_CHANGE = "no_strength_change"
    NO_FORM_OR_STRENGTH_CHANGE = "no_form_or_strength_change"
    BRAND_REQUESTED_BY_PATIENT = "brand_requested_by_patient"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.NO_GENERIC: "3",
            self.NO_FORM_CHANGE: "4",
            self.NO_STRENGTH_CHANGE: "5",
            self.NO_FORM_OR_STRENGTH_CHANGE: "6",
            self.BRAND_REQUESTED_BY_PATIENT: "8",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NO_GENERIC: "後発品変更不可",
            self.NO_FORM_CHANGE: "剤形変更不可",
            self.NO_STRENGTH_CHANGE: "含量規格変更不可",
            self.NO_FORM_OR_STRENGTH_CHANGE: "剤形変更不可及び含量規格変更不可",
            self.BRAND_REQUESTED_BY_PATIENT: "先発医薬品患者希望",
        }
        return labels[self]

    @property
    def forbids_generic_substitution(self) -> bool:
        """後発医薬品への変更調剤を禁じる指示か。"""
        return self in (
            GenericSubstitutionRestrictionType.NO_GENERIC,
            GenericSubstitutionRestrictionType.BRAND_REQUESTED_BY_PATIENT,
        )


class InquiryNumber(BasePositiveInt):
    """疑義照会の連番。

    規格（調剤編 511）は「複数記録可（最大999）」なので上限を999に揃える。
    99に絞る業務上の根拠がない。
    """

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("照会連番は999以内で指定してください。")


class InquiryResultType(StrEnum):
    """疑義照会の結果区分。"""

    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    DELETED = "deleted"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.MODIFIED: "処方変更",
            self.UNCHANGED: "疑義解消・変更なし調剤",
            self.DELETED: "処方削除",
        }
        return labels[self]

    @property
    def blocks_dispensing(self) -> bool:
        """この結果により当該処方の調剤ができなくなるか。"""
        return self is InquiryResultType.DELETED


class DosageCodeType(StrEnum):
    """用法コード種別。

    JAHIS レコードNo.111 は「1:コードなし, 2:JAMI用法コード, 3〜8:将来統一
    コードを想定」。処方編の用法レコードは「``3``（電子処方箋用法マスタ）固定」。
    **紙と電子で使える値が異なる。**
    """

    NONE = "none"
    JAMI = "jami"
    EP_MASTER = "ep_master"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        return {self.NONE: "1", self.JAMI: "2", self.EP_MASTER: "3"}[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NONE: "コードなし",
            self.JAMI: "JAMI用法コード",
            self.EP_MASTER: "電子処方箋用法マスタ",
        }
        return labels[self]


class DosageCode(BaseNormalizedString):
    """用法コード。JAHIS・処方編とも ``X16``（16桁）。

    JAMI（日本医療情報学会）の処方・注射オーダ標準用法規格、または
    電子処方箋用法マスタのコード。例: ``1013044400000000``。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) != 16:
            raise DomainValidationError("用法コードは16桁で指定してください。")


class DosageName(BaseNormalizedString):
    """用法名称。JAHIS は ``N50``、処方編は ``N150``。広い方に合わせる。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 150:
            raise DomainValidationError("用法名称は150文字以内で指定してください。")


class DailyFrequency(BasePositiveInt):
    """1日回数。JAHIS レコードNo.111 のフィールドは ``92 2`` なので 1〜99。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 99:
            raise DomainValidationError("1日回数は99以内で指定してください。")


class _MedicineCodeComparison(Enum):
    """記録された薬品コードの一致・不一致・比較不能を表す。"""

    MATCH = auto()
    MISMATCH = auto()
    UNKNOWN = auto()
