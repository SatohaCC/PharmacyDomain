"""利用側が所有する不変の参照情報。元コンテキストの実装型は保持しない。"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseNormalizedString,
    BasePositiveDecimal,
    BasePositiveInt,
)


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
