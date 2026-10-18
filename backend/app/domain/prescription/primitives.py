"""prescriptionの単一値と列挙・検証規則。"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseAddress,
    BaseAwareTimestamp,
    BaseDate,
    BaseFreeText,
    BaseNormalizedString,
    BasePositiveDecimal,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    ensure_digits,
)


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


class InteractionSeverity(StrEnum):
    """相互作用の重大度・区分。"""

    CONTRAINDICATED = "contraindicated"
    PRECAUTION = "precaution"
    NONE = "none"

    @property
    def label(self) -> str:
        """日本語表示ラベル。"""
        labels = {
            self.CONTRAINDICATED: "併用禁忌",
            self.PRECAUTION: "併用注意",
            self.NONE: "相互作用なし",
        }
        return labels[self]


# --------------------------------------------------------------------------
# 処方箋記載の剤・数量・用量
# --------------------------------------------------------------------------


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


class SingleDoseAmount(BasePositiveDecimal):
    """処方箋に記載する1回あたりの服用量。

    JAHISレコードNo.241の1回服用量に対応する。``DosageAmount`` と意味が異なる
    ため別の型にする。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "1回服用量"


class ConversionFactor(BasePositiveDecimal):
    """処方箋表記単位から薬価収載単位への変換係数。

    薬価収載単位用量は「処方用量 × 単位変換係数」で求める。JAHISレコード
    No.211の単位変換レコードに対応する。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "単位変換係数"


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


# --------------------------------------------------------------------------
# 処方箋の受領元と状態
# --------------------------------------------------------------------------


class PrescriptionSourceType(StrEnum):
    """処方箋の受領元形式。

    使用可能な薬品コード種別の集合を決めるため、単なる区分ではなく
    不変条件の入力になる（``Prescription.validate()``）。
    """

    PAPER_QR = "paper_qr"
    ELECTRONIC = "electronic"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.PAPER_QR: "紙処方箋（2次元シンボル）",
            self.ELECTRONIC: "電子処方箋",
        }
        return labels[self]


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


class PrescriptionDocumentNumber(BaseNormalizedString):
    """処方箋ID。

    電子処方箋引換番号（16桁数字）、電子処方箋管理サービスが発行するUUID（36文字）、
    紙処方箋の番号のいずれも入る。**形式は規格ごとに異なるため桁数は課さず**、
    長さの上限だけを持つ。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 36:
            raise DomainValidationError("処方箋IDは36文字以内で指定してください。")


# --------------------------------------------------------------------------
# 医療機関（JAHIS レコードNo.1 / No.2）
# --------------------------------------------------------------------------


class MedicalInstitutionCodeType(StrEnum):
    """医療機関コード種別。

    出典: JAHIS Ver.1.11 レコードNo.1 備考欄「1:医科、3:歯科、6:訪問、省略:医科」。
    処方編は別表1「点数表コード」。省略時は医科として扱う。
    """

    MEDICAL = "medical"
    DENTAL = "dental"
    HOME_VISIT = "home_visit"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {self.MEDICAL: "1", self.DENTAL: "3", self.HOME_VISIT: "6"}
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.MEDICAL: "医科", self.DENTAL: "歯科", self.HOME_VISIT: "訪問"}
        return labels[self]


class MedicalInstitutionCode(BaseNormalizedString):
    """保険医療機関コード（レセプト提出用コード）。

    JAHIS レコードNo.1 で ``X7``。``9999999`` は職域診療所の特例。
    """

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="医療機関コード", lengths=(7,))


class MedicalInstitutionPrefectureCode(BaseNormalizedString):
    """医療機関都道府県コード。

    出典: JAHIS 別表1「都道府県コード」/ 処方編 別表2。JIS X 0401 の 01〜47。
    """

    def validate(self) -> None:
        super().validate()
        ensure_digits(self.value, field_name="医療機関都道府県コード", lengths=(2,))
        if not 1 <= int(self.value) <= 47:
            raise DomainValidationError(
                "医療機関都道府県コードは01から47の範囲で指定してください。"
            )


class MedicalInstitutionName(BaseNormalizedString):
    """医療機関名称。JAHIS レコードNo.1 で ``N60``（漢字半角混在可）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 60:
            raise DomainValidationError("医療機関名称は60文字以内で指定してください。")


class MedicalInstitutionPostalCode(BasePostalCode):
    """医療機関の郵便番号。"""


class MedicalInstitutionAddressLine(BaseAddress):
    """医療機関の所在地。"""


class MedicalInstitutionPhoneNumber(BaseTelephoneNumber):
    """医療機関の電話番号。"""

    field_name: ClassVar[str] = "医療機関電話番号"


class MedicalInstitutionFaxNumber(BaseTelephoneNumber):
    """医療機関のFAX番号。"""

    field_name: ClassVar[str] = "医療機関FAX番号"


# --------------------------------------------------------------------------
# 診療科・処方医（JAHIS レコードNo.4 / No.5）
# --------------------------------------------------------------------------


class DepartmentCodeType(StrEnum):
    """診療科コード種別。

    出典: JAHIS Ver.1.11 レコードNo.4 備考欄「1:コードなし、2:診療科コード
    （科名省略可）、3〜8:将来統一コードを想定、省略:コードなし」/ 処方編 別表3。
    """

    NONE = "none"
    STANDARD = "standard"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        return {self.NONE: "1", self.STANDARD: "2"}[self]


class DepartmentCode(BaseNormalizedString):
    """診療科コード。

    JAHIS レコードNo.4 のフィールドは ``X6`` だが、別表3（処方編は別表4）が
    定める値は2桁である（01:内科, 02:精神科, 09:小児科, 10:外科, 19:皮膚科,
    23:産婦人科, 26:眼科, 27:耳鼻いんこう科, 31:麻酔科 等）。
    **フィールド長で検証する**（別表の値だけに限定すると、将来の追加で
    正当なコードを弾く）。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 6:
            raise DomainValidationError("診療科コードは6文字以内で指定してください。")
        if not re.fullmatch(r"[0-9A-Za-z]+", self.value):
            raise DomainValidationError("診療科コードは半角英数字で指定してください。")


class DepartmentName(BaseNormalizedString):
    """診療科名。JAHIS レコードNo.4 で ``N40``（漢字半角混在可）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 40:
            raise DomainValidationError("診療科名は40文字以内で指定してください。")


class PrescriberCode(BaseNormalizedString):
    """処方医コード（医療機関内の医師識別子）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 20:
            raise DomainValidationError("処方医コードは20文字以内で指定してください。")


class PrescriberName(BaseNormalizedString):
    """処方医氏名（疑義照会の回答者名など、姓名を分離しない用途）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 40:
            raise DomainValidationError("処方医氏名は40文字以内で指定してください。")


# --------------------------------------------------------------------------
# 処方期間（JAHIS レコードNo.11 / No.12）
# --------------------------------------------------------------------------


class PrescriptionIssuedDate(BaseDate):
    """処方箋交付年月日。"""


class PrescriptionValidTo(BaseDate):
    """処方箋の使用期限（当日を含む）。"""


# --------------------------------------------------------------------------
# 用法（JAHIS レコードNo.111 / 処方編 別表14）
# --------------------------------------------------------------------------


class DosageFormName(BaseNormalizedString):
    """剤形名称。剤形区分が「9:不明」の場合のみ任意で記録する。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 20:
            raise DomainValidationError("剤形名称は20文字以内で指定してください。")


class DosageSupplementType(StrEnum):
    """用法補足区分。

    出典: 処方編 別表14 / JAHIS レコードNo.181。両規格で値は一致する。
    RP全体に掛かる補足であり、薬品単位の補足は :class:`MedicineSupplementType`。
    """

    TAPERING = "tapering"
    UNIT_DOSE = "unit_dose"
    ALTERNATE_DAY = "alternate_day"
    CRUSHED = "crushed"
    CONTINUATION = "continuation"
    SITE = "site"
    SINGLE_DOSE = "single_dose"
    JAMI_SUPPLEMENT = "jami_supplement"
    JAMI_SITE = "jami_site"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.TAPERING: "1",
            self.UNIT_DOSE: "2",
            self.ALTERNATE_DAY: "3",
            self.CRUSHED: "4",
            self.CONTINUATION: "5",
            self.SITE: "6",
            self.SINGLE_DOSE: "7",
            self.JAMI_SUPPLEMENT: "8",
            self.JAMI_SITE: "9",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.TAPERING: "漸減",
            self.UNIT_DOSE: "一包化",
            self.ALTERNATE_DAY: "隔日",
            self.CRUSHED: "粉砕",
            self.CONTINUATION: "用法の続き",
            self.SITE: "部位",
            self.SINGLE_DOSE: "1回使用量",
            self.JAMI_SUPPLEMENT: "JAMI補足用法（不均等を除く）",
            self.JAMI_SITE: "JAMI部位",
        }
        return labels[self]


class DosageSupplementText(BaseNormalizedString):
    """用法補足情報。JAHIS レコードNo.181 で ``N50``。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 50:
            raise DomainValidationError("用法補足情報は50文字以内で指定してください。")


class DosageSupplementCode(BaseNormalizedString):
    """補足用法コード。用法補足区分が「8:JAMI補足用法」の場合に記録する（``X8``）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 8:
            raise DomainValidationError("補足用法コードは8文字以内で指定してください。")


class ApplicationSiteCode(BaseNormalizedString):
    """外用部位コード。用法補足区分が「9:JAMI部位」の場合に必須（``X3``）。

    点眼（両眼/左眼/右眼）、点耳（左耳/右耳）、貼付部位など。例: ``42L``（左耳）。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) != 3:
            raise DomainValidationError("外用部位コードは3文字で指定してください。")


# --------------------------------------------------------------------------
# 薬品補足・変更制限（処方編 別表16 / JAHIS レコードNo.281）
# --------------------------------------------------------------------------


class MedicineSupplementType(StrEnum):
    """薬品補足区分のうち**調製指示**にあたる値。

    出典: 処方編 別表16 / JAHIS レコードNo.281。同じ enum に変更制限
    （3〜6・8）が混在しているが、性質が違うので
    :class:`GenericSubstitutionRestrictionType` へ分けている。
    振り分けの重複は ``PrescriptionMedicine.validate()`` が拒否する。
    """

    UNIT_DOSE = "unit_dose"
    CRUSHED = "crushed"
    JAMI_SUPPLEMENT = "jami_supplement"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        return {self.UNIT_DOSE: "1", self.CRUSHED: "2", self.JAMI_SUPPLEMENT: "7"}[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.UNIT_DOSE: "一包化",
            self.CRUSHED: "粉砕",
            self.JAMI_SUPPLEMENT: "JAMI補足用法（不均等を除く）",
        }
        return labels[self]


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


#: 処方編 別表16「薬品補足区分」が定義するコードの全体（9〜99は未使用）。
_SUPPLEMENT_RECORD_CODES = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})


def verify_supplement_code_partition(
    *, supplement_codes: set[str], restriction_codes: set[str]
) -> None:
    """別表16 のコードが調製指示と変更制限へ重複なく分割されていることを検証する。

    規格は両者を1本の enum で定義しており、本モデルは性質で2つの型へ分けている。
    **分割が崩れる（同じコードが両方に現れる／どちらにも無い）と、薬品補足を
    規格へ往復変換したときにどちらの型へ戻すかが決まらない。**

    危険なのは実行時の個別インスタンスではない（型が分かれている以上、
    1つの薬品明細で両方に同じコードが入ることはありえない）。危険なのは
    後から enum へ値を足すときなので、モジュール読み込み時に検証する。

    最適化実行（``python -O``）でも省略されないよう ``assert`` ではなく
    ``RuntimeError`` を送出する（``access_control/policy.py`` と同じ方式）。
    検証内容を引数で受けるのは、この関数自体をテストできるようにするため。
    """
    overlap = supplement_codes & restriction_codes
    if overlap:
        raise RuntimeError(
            "別表16のコードが薬品補足区分と変更制限区分の両方に定義されています: "
            f"{sorted(overlap)}。"
        )
    covered = supplement_codes | restriction_codes
    if covered != _SUPPLEMENT_RECORD_CODES:
        missing = sorted(_SUPPLEMENT_RECORD_CODES - covered)
        extra = sorted(covered - _SUPPLEMENT_RECORD_CODES)
        raise RuntimeError(
            "別表16のコードの分割に漏れまたは余剰があります。"
            f"未定義: {missing}、規格外: {extra}。"
        )


class MedicineSupplementText(BaseNormalizedString):
    """薬品補足情報。JAHIS レコードNo.281 で ``N50``。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 50:
            raise DomainValidationError("薬品補足情報は50文字以内で指定してください。")


class SubstitutionRestrictionReason(BaseFreeText):
    """変更不可とした理由（保険医の記載）。"""


# --------------------------------------------------------------------------
# 処方管理・特殊指示
# --------------------------------------------------------------------------


class RefillCount(BasePositiveInt):
    """リフィル処方箋の総使用回数。

    保険調剤の理解のために（令和8年度）「リフィル処方箋による1回目又は
    2回目（総使用回数3回の場合）の調剤」より、2回または3回のみ。
    1回はリフィル処方箋ではない。
    """

    def validate(self) -> None:
        super().validate()
        if self.value not in (2, 3):
            raise DomainValidationError(
                "リフィル処方箋の総使用回数は2回または3回で指定してください。"
            )


class SplitCount(BasePositiveInt):
    """医師の分割指示（調剤基本料「注11」）における全分割回数。2〜3回。"""

    def validate(self) -> None:
        super().validate()
        if self.value not in (2, 3):
            raise DomainValidationError(
                "分割指示の全分割回数は2回または3回で指定してください。"
            )


class SplitIteration(BasePositiveInt):
    """当該分割回。1から ``SplitCount`` まで。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 3:
            raise DomainValidationError("分割回は3以内で指定してください。")


class NarcoticLicenseNumber(BaseNormalizedString):
    """麻薬施用者免許番号。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 20:
            raise DomainValidationError(
                "麻薬施用者免許番号は20文字以内で指定してください。"
            )


class PatientAddressLine(BaseAddress):
    """麻薬処方箋に記載される患者住所。"""


class PatientPhoneNumber(BaseTelephoneNumber):
    """麻薬処方箋に記載される患者電話番号。"""

    field_name: ClassVar[str] = "患者電話番号"


class ResidualDrugInstruction(StrEnum):
    """残薬確認対応フラグ。

    出典: 処方編 別表11。コード ``2`` は2026年6月に意味が変わっており、
    本モデルは**2026年6月以降の解釈**（減数調剤指示）を採る。過去処方箋を
    取り込む場合は交付日に応じた解釈が必要になるため、``ResidualDrugConfirmation``
    は交付日とセットで解釈すること。
    """

    INQUIRE_AND_DISPENSE = "inquire_and_dispense"
    REDUCE_AND_INFORM = "reduce_and_inform"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        return {self.INQUIRE_AND_DISPENSE: "1", self.REDUCE_AND_INFORM: "2"}[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称（2026年6月以降）。"""
        labels = {
            self.INQUIRE_AND_DISPENSE: "保険医療機関へ疑義照会した上で調剤",
            self.REDUCE_AND_INFORM: (
                "調剤する薬剤を減量した上で保険医療機関に情報提供"
            ),
        }
        return labels[self]


class PrescriptionNote(BaseFreeText):
    """処方箋全体に係る備考。JAHIS レコードNo.81 備考レコード。"""


class ClinicalInformationText(BaseFreeText):
    """臨床情報（診断名・症状等）。電子処方箋で医師が任意に付す。"""


class LaboratoryDataText(BaseFreeText):
    """検査値情報（腎機能・肝機能等）。用量調整の判断根拠。"""


# --------------------------------------------------------------------------
# 疑義照会（調剤編 疑義照会結果レコード(511)）
# --------------------------------------------------------------------------


class InquiryNumber(BasePositiveInt):
    """疑義照会の連番。

    規格（調剤編 511）は「複数記録可（最大999）」なので上限を999に揃える。
    99に絞る業務上の根拠がない。
    """

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("照会連番は999以内で指定してください。")


class InquiryCategory(StrEnum):
    """疑義照会の種別。

    **規格由来ではない。** 調剤編 別表7「疑義照会種別コード」は現状
    ``999:その他`` のみで、他は「（今後追加予定）」である。検索・分類のために
    独自定義し、規格へ送信する際は全件 ``999`` に畳む。
    """

    DOSAGE = "dosage"
    INTERACTION = "interaction"
    DUPLICATION = "duplication"
    RESIDUAL_DRUG = "residual_drug"
    CONTRAINDICATION = "contraindication"
    GENERIC_SUBSTITUTION = "generic_substitution"
    INCOMPLETE_DESCRIPTION = "incomplete_description"
    OTHER = "other"

    @property
    def record_code(self) -> str:
        """規格（調剤編 別表7）へ記録するコード。現状はすべて ``999``。"""
        return "999"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.DOSAGE: "用法用量",
            self.INTERACTION: "相互作用",
            self.DUPLICATION: "重複投薬",
            self.RESIDUAL_DRUG: "残薬調整",
            self.CONTRAINDICATION: "禁忌",
            self.GENERIC_SUBSTITUTION: "後発品変更",
            self.INCOMPLETE_DESCRIPTION: "記載不備",
            self.OTHER: "その他",
        }
        return labels[self]


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


class InquiryContent(BaseFreeText):
    """疑義照会の内容。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("疑義照会内容は空にできません。")
        if len(self.value) > 600:
            raise DomainValidationError("疑義照会内容は600文字以内で指定してください。")


class InquiryResponseContent(BaseFreeText):
    """疑義照会に対する回答内容。"""

    def validate(self) -> None:
        super().validate()
        if not self.value:
            raise DomainValidationError("疑義照会の回答内容は空にできません。")
        if len(self.value) > 600:
            raise DomainValidationError(
                "疑義照会の回答内容は600文字以内で指定してください。"
            )


class InquiryTimestamp(BaseAwareTimestamp):
    """疑義照会の照会・回答を記録したUTC時刻。

    注入された ``Clock`` 由来の値を受け取る。
    """

    timestamp_name: ClassVar[str] = "照会日時"


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


class YjCode(BaseNormalizedString):
    """厚生労働省薬価基準収載医薬品コード（YJコード、12桁英数字）。"""

    def _normalize(self, value: str) -> str:
        if not isinstance(value, str):
            raise DomainValidationError("YJコードは文字列である必要があります。")
        nfkc = unicodedata.normalize("NFKC", value)
        return super()._normalize(nfkc).upper()

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("YJコードは空にできません。")
        if not re.fullmatch(r"^[0-9A-Z]{12}$", self.value):
            raise DomainValidationError(
                f"YJコードは12桁の半角英数字である必要があります。指定された値: '{self.value}'"
            )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, YjCode):
            return NotImplemented
        return self.value < other.value


# --------------------------------------------------------------------------
# 医薬品マスタから受け取る事実
# --------------------------------------------------------------------------


class MedicineRestrictionFlag(StrEnum):
    """医薬品の規制属性の有無。

    ``UNKNOWN`` を**明示的に持つ**のが要点である。これらの属性は処方箋2次元
    シンボルにも電子処方箋にも含まれず（流れてくるのは薬品コードと名称だけ）、
    判定には医薬品マスタが要る。マスタに載っていない薬品を「該当しない」と
    黙って扱うと、麻薬処方箋の必須項目チェックやリフィル適用除外の判定が
    素通りする。分からないことを分からないと言える型にしておき、
    判定側は ``UNKNOWN`` を拒否する（fail-closed）。
    """

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"

    @property
    def is_unknown(self) -> bool:
        """判定に必要な情報が得られていないか。"""
        return self is MedicineRestrictionFlag.UNKNOWN

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.YES: "該当", self.NO: "非該当", self.UNKNOWN: "不明"}
        return labels[self]


def _ensure_consecutive_from_one(numbers: tuple[int, ...]) -> bool:
    """1から連続した昇順に並んでいるかを返す。"""
    return list(numbers) == list(range(1, len(numbers) + 1))
