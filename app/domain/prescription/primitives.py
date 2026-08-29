"""Prescriptionコンテキストの識別子・処方情報プリミティブ。

規格の出典は2系統ある。**別表番号は規格ごとに異なるので、出典は規格名まで書く**
（``okf/rules.md`` §4.5）。

- JAHIS 院外処方箋２次元シンボル記録条件規約 Ver.1.11 … レコード番号と備考欄
- 厚労省 電子処方箋管理サービス 記録条件仕様（処方編）Ver.2.4 … 別表1〜16

薬品そのものの語彙（``MedicineName`` / ``DosageAmount`` 等）は所有者がいないため
Shared Kernel の ``app/base/domain/medicine.py`` にある。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import ClassVar

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseAddress,
    BaseAwareTimestamp,
    BaseDate,
    BaseFreeText,
    BaseNormalizedString,
    BasePositiveInt,
    BasePostalCode,
    BaseTelephoneNumber,
    EntityUUID,
    ensure_digits,
)

# --------------------------------------------------------------------------
# 識別子
# --------------------------------------------------------------------------


class PrescriptionId(EntityUUID):
    """処方箋集約の一意識別子（UUIDv7）。"""

    identifier_name = "処方箋ID"


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


verify_supplement_code_partition(
    supplement_codes={member.record_code for member in MedicineSupplementType},
    restriction_codes={
        member.record_code for member in GenericSubstitutionRestrictionType
    },
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
