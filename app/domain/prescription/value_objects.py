"""Prescriptionコンテキストの複合 Value Object。

処方箋の構成要素のうち、複数のプリミティブを束ねて1つの概念になるもの。
集約とその子要素（``PrescriptionRp`` / ``PrescriptionMedicine`` /
``PrescriptionInquiry``）は ``prescription.py`` にある。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import ClassVar

from app.base.domain.medicine import (
    ConversionFactor,
    DosageAmount,
    MedicineIdentifier,
    MedicineUnit,
)
from app.base.domain.value_object import PersonNames, ValueObject
from app.domain.prescription.exceptions import (
    ApplicationSiteCodeRequiredError,
    DepartmentCodeRequiredError,
    DosageSupplementCodeRequiredError,
    PrescriptionPeriodInvertedError,
    SplitIterationOutOfRangeError,
    UnequalDosageTotalMismatchError,
)
from app.domain.prescription.primitives import (
    ApplicationSiteCode,
    ClinicalInformationText,
    DepartmentCode,
    DepartmentCodeType,
    DepartmentName,
    DosageSupplementCode,
    DosageSupplementText,
    DosageSupplementType,
    GenericSubstitutionRestrictionType,
    InquiryResponseContent,
    InquiryResultType,
    InquiryTimestamp,
    LaboratoryDataText,
    MedicalInstitutionAddressLine,
    MedicalInstitutionCode,
    MedicalInstitutionCodeType,
    MedicalInstitutionFaxNumber,
    MedicalInstitutionName,
    MedicalInstitutionPhoneNumber,
    MedicalInstitutionPostalCode,
    MedicalInstitutionPrefectureCode,
    MedicineSupplementText,
    MedicineSupplementType,
    NarcoticLicenseNumber,
    PatientAddressLine,
    PatientPhoneNumber,
    PrescriberCode,
    PrescriberName,
    PrescriptionIssuedDate,
    PrescriptionNote,
    PrescriptionValidTo,
    RefillCount,
    ResidualDrugInstruction,
    SplitCount,
    SplitIteration,
    SubstitutionRestrictionReason,
)

#: 使用期限の指定がない場合の実効日数。交付日を含めて4日間。
#: 出典: 保険調剤の理解のために（令和8年度）「処方箋の使用期間は、交付の日を
#: 含めて４日以内とされている」。
DEFAULT_VALID_DAYS = 4


@dataclass(frozen=True, kw_only=True)
class MedicalInstitutionInfo(ValueObject):
    """処方箋を交付した保険医療機関の情報。

    出典: JAHIS レコードNo.1（医療機関レコード）/ No.2（医療機関所在地レコード）。
    """

    code_type: MedicalInstitutionCodeType
    code: MedicalInstitutionCode
    prefecture_code: MedicalInstitutionPrefectureCode
    name: MedicalInstitutionName
    postal_code: MedicalInstitutionPostalCode | None = None
    address: MedicalInstitutionAddressLine | None = None
    phone_number: MedicalInstitutionPhoneNumber | None = None
    fax_number: MedicalInstitutionFaxNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code_type": "医療機関コード種別",
        "code": "医療機関コード",
        "prefecture_code": "医療機関都道府県コード",
        "name": "医療機関名称",
        "postal_code": "郵便番号",
        "address": "所在地",
        "phone_number": "電話番号",
        "fax_number": "FAX番号",
    }


@dataclass(frozen=True, kw_only=True)
class DepartmentInfo(ValueObject):
    """診療科の情報。

    出典: JAHIS レコードNo.4（診療科レコード）。診療所および単科病院では
    未出力可だが、本モデルは科名を必須として扱う（薬歴の法定記載事項
    「処方した保険医療機関名、処方医氏名」の運用上、科名は常に要るため）。
    """

    code_type: DepartmentCodeType
    name: DepartmentName
    code: DepartmentCode | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code_type": "診療科コード種別",
        "name": "診療科名",
        "code": "診療科コード",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。"""
        if self.code_type is DepartmentCodeType.STANDARD and self.code is None:
            raise DepartmentCodeRequiredError()
        if self.code_type is DepartmentCodeType.NONE and self.code is not None:
            raise DepartmentCodeRequiredError(
                "診療科コード種別が「コードなし」のときは診療科コードを指定できません。"
            )


@dataclass(frozen=True, kw_only=True)
class PrescriberInfo(ValueObject):
    """処方医の情報。

    出典: JAHIS レコードNo.5（医師レコード）。漢字氏名は必須。
    """

    names: PersonNames
    code: PrescriberCode | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "names": "処方医氏名",
        "code": "処方医コード",
    }


@dataclass(frozen=True, kw_only=True)
class PrescriptionPeriod(ValueObject):
    """処方箋の交付日と使用期限。

    使用期限は**当日を含む**。適用日の判定は必ず引数で受け取り、
    ``date.today()`` を暗黙に使わない（ruff ``DTZ011`` が禁止している）。
    """

    issued_date: PrescriptionIssuedDate
    valid_to: PrescriptionValidTo

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "issued_date": "処方箋交付年月日",
        "valid_to": "使用期限",
    }

    def validate(self) -> None:
        """使用期限が交付日以降であることを検証する。"""
        if self.valid_to.value < self.issued_date.value:
            raise PrescriptionPeriodInvertedError()

    @classmethod
    def with_default_validity(
        cls, issued_date: PrescriptionIssuedDate
    ) -> PrescriptionPeriod:
        """使用期限の指定がない場合の既定値（交付日を含めて4日間）で生成する。"""
        return cls(
            issued_date=issued_date,
            valid_to=PrescriptionValidTo(
                issued_date.value + timedelta(days=DEFAULT_VALID_DAYS - 1)
            ),
        )

    def is_expired_on(self, target_date: date) -> bool:
        """指定日時点で使用期限を過ぎているかを返す。"""
        return target_date > self.valid_to.value

    def includes(self, target_date: date) -> bool:
        """指定日が交付日から使用期限までの範囲に含まれるかを返す。"""
        return self.issued_date.value <= target_date <= self.valid_to.value


@dataclass(frozen=True, kw_only=True)
class RefillInstruction(ValueObject):
    """リフィル処方箋の指示。

    適用除外（投与量に限度が定められている医薬品・貼付剤）の判定は
    医薬品マスタ側の属性であり、この Value Object では判定できない。
    ``RefillEligibilityService`` が ``MedicineRestrictionBoundary`` を使って行う。
    """

    total_refill_count: RefillCount

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "total_refill_count": "リフィル総使用回数",
    }


@dataclass(frozen=True, kw_only=True)
class SplitInstruction(ValueObject):
    """医師の分割指示（調剤基本料「注11」）。

    薬局判断による分割調剤（注9 長期保存の困難性等 / 注10 後発医薬品の試用）は
    処方箋の属性ではないため、ここには現れない（Dispensingコンテキストの
    ``split_reason`` が持つ）。
    """

    total_split_count: SplitCount
    split_iteration: SplitIteration

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "total_split_count": "全分割回数",
        "split_iteration": "当該分割回",
    }

    def validate(self) -> None:
        """当該分割回が全分割回数の範囲内であることを検証する。"""
        if self.split_iteration.value > self.total_split_count.value:
            raise SplitIterationOutOfRangeError(
                total=self.total_split_count.value,
                iteration=self.split_iteration.value,
            )


@dataclass(frozen=True, kw_only=True)
class NarcoticPrescriptionDetails(ValueObject):
    """麻薬処方箋に必要な追加情報。

    麻薬及び向精神薬取締法により、麻薬処方箋には患者の住所と
    麻薬施用者免許番号の記載が必要になる。
    """

    narcotic_license_number: NarcoticLicenseNumber
    patient_address: PatientAddressLine
    patient_phone_number: PatientPhoneNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "narcotic_license_number": "麻薬施用者免許番号",
        "patient_address": "患者住所",
        "patient_phone_number": "患者電話番号",
    }


@dataclass(frozen=True, kw_only=True)
class ResidualDrugConfirmation(ValueObject):
    """残薬確認の指示（処方編 別表11）。"""

    instruction: ResidualDrugInstruction

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"instruction": "残薬確認対応"}

    @property
    def requires_inquiry(self) -> bool:
        """調剤前に保険医療機関への疑義照会を要する指示か。"""
        return self.instruction is ResidualDrugInstruction.INQUIRE_AND_DISPENSE

    @property
    def allows_reduction(self) -> bool:
        """減数調剤を認める指示か。"""
        return self.instruction is ResidualDrugInstruction.REDUCE_AND_INFORM


@dataclass(frozen=True, kw_only=True)
class ClinicalInformation(ValueObject):
    """臨床情報（診断名・症状等）。"""

    text: ClinicalInformationText

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"text": "臨床情報"}


@dataclass(frozen=True, kw_only=True)
class LaboratoryData(ValueObject):
    """検査値情報（腎機能・肝機能等）。"""

    text: LaboratoryDataText

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"text": "検査値情報"}


@dataclass(frozen=True, kw_only=True)
class PrescriptionNotes(ValueObject):
    """処方箋全体に係る備考のファーストクラスコレクション。"""

    items: tuple[PrescriptionNote, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"items": "備考"}

    @property
    def is_empty(self) -> bool:
        """備考が1件も無いか。"""
        return not self.items


@dataclass(frozen=True, kw_only=True)
class PrescriptionManagementInfo(ValueObject):
    """処方箋の管理情報・特殊指示をまとめた Value Object。"""

    refill: RefillInstruction | None = None
    split: SplitInstruction | None = None
    narcotic: NarcoticPrescriptionDetails | None = None
    residual_drug: ResidualDrugConfirmation | None = None
    notes: PrescriptionNotes = PrescriptionNotes()
    clinical_info: tuple[ClinicalInformation, ...] = ()
    lab_data: tuple[LaboratoryData, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "refill": "リフィル指示",
        "split": "分割指示",
        "narcotic": "麻薬処方箋情報",
        "residual_drug": "残薬確認指示",
        "notes": "備考",
        "clinical_info": "臨床情報",
        "lab_data": "検査値情報",
    }

    @property
    def is_refill(self) -> bool:
        """リフィル処方箋か。"""
        return self.refill is not None

    @property
    def is_split(self) -> bool:
        """医師の分割指示に係る処方箋か。"""
        return self.split is not None


@dataclass(frozen=True, kw_only=True)
class DosageSupplement(ValueObject):
    """用法補足（JAHIS レコードNo.181 / 処方編 別表14）。

    RP全体に掛かる補足情報。薬品単位の補足は :class:`MedicineSupplement`。
    """

    supplement_type: DosageSupplementType
    text: DosageSupplementText
    code: DosageSupplementCode | None = None
    site_code: ApplicationSiteCode | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "supplement_type": "用法補足区分",
        "text": "用法補足情報",
        "code": "補足用法コード",
        "site_code": "外用部位コード",
    }

    def validate(self) -> None:
        """区分ごとに必須となるコードの有無を検証する。"""
        if (
            self.supplement_type is DosageSupplementType.JAMI_SUPPLEMENT
            and self.code is None
        ):
            raise DosageSupplementCodeRequiredError(
                "用法補足区分が「JAMI補足用法（不均等を除く）」のときは"
                "補足用法コードが必要です。"
            )
        if self.supplement_type is DosageSupplementType.JAMI_SITE and (
            self.site_code is None
        ):
            raise ApplicationSiteCodeRequiredError()


@dataclass(frozen=True, kw_only=True)
class MedicineSupplement(ValueObject):
    """薬品補足のうち**調製指示**（処方編 別表16 の 1・2・7）。

    変更制限（3〜6・8）は :class:`GenericSubstitutionRestriction` が持つ。
    同一薬品で同じコードが両方に現れないことは
    ``PrescriptionMedicine.validate()`` が拒否する。
    """

    supplement_type: MedicineSupplementType
    text: MedicineSupplementText
    code: DosageSupplementCode | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "supplement_type": "薬品補足区分",
        "text": "薬品補足情報",
        "code": "補足用法コード",
    }

    def validate(self) -> None:
        """JAMI補足用法のときはコードが必要であることを検証する。"""
        if (
            self.supplement_type is MedicineSupplementType.JAMI_SUPPLEMENT
            and self.code is None
        ):
            raise DosageSupplementCodeRequiredError(
                "薬品補足区分が「JAMI補足用法（不均等を除く）」のときは"
                "補足用法コードが必要です。"
            )


@dataclass(frozen=True, kw_only=True)
class GenericSubstitutionRestriction(ValueObject):
    """薬品補足のうち**変更制限**（処方編 別表16 の 3〜6・8）。"""

    restriction_type: GenericSubstitutionRestrictionType
    reason: SubstitutionRestrictionReason | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "restriction_type": "変更制限区分",
        "reason": "変更不可の理由",
    }

    @property
    def forbids_generic_substitution(self) -> bool:
        """後発医薬品への変更調剤を禁じるか。"""
        return self.restriction_type.forbids_generic_substitution


@dataclass(frozen=True, kw_only=True)
class UnitConversion(ValueObject):
    """単位変換（JAHIS レコードNo.211 単位変換レコード）。

    処方箋表記単位が官報告示薬価収載単位と異なる場合に記録する。
    ``薬価収載単位用量 = 処方用量 × 単位変換係数``。
    """

    factor: ConversionFactor
    tariff_unit: MedicineUnit

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "factor": "単位変換係数",
        "tariff_unit": "薬価収載単位",
    }

    def convert(self, amount: DosageAmount) -> DosageAmount:
        """処方用量を薬価収載単位の用量へ換算する。"""
        return DosageAmount(amount.value * self.factor.value)


@dataclass(frozen=True, kw_only=True)
class UnequalDosageInstruction(ValueObject):
    """不均等服用指示（JAHIS レコードNo.221 不均等レコード）。

    朝・昼・夕・就寝前などで服用量が異なる場合の指示。
    **各回服用量の合計は薬品の1日量と厳密に一致しなければならない。**
    この判定のために用量は ``Decimal`` である（``float`` では実在する用量刻みの
    12.7% で合計が一致せず、正当な処方を弾く）。
    """

    doses: tuple[DosageAmount, ...]

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"doses": "各回服用量"}

    def validate(self) -> None:
        """少なくとも2回分の指示があることを検証する。"""
        if len(self.doses) < 2:
            raise UnequalDosageTotalMismatchError(
                "不均等服用指示は2回分以上の服用量が必要です。"
            )

    @property
    def total(self) -> DosageAmount:
        """各回服用量の合計。"""
        total = self.doses[0].value
        for dose in self.doses[1:]:
            total += dose.value
        return DosageAmount(total)

    def matches_daily_amount(self, daily_amount: DosageAmount) -> bool:
        """合計が1日量と一致するかを返す。"""
        return self.total.value == daily_amount.value


@dataclass(frozen=True, kw_only=True)
class PrescriberResponse(ValueObject):
    """疑義照会に対する処方医の回答。

    回答が存在する場合にのみ生成される。未回答は
    ``PrescriptionInquiry.response is None`` で表す。

    処方変更前後のスナップショットは保持しない。処方箋自身の中に自分の
    スナップショットを持つのは自己参照であり、どちらが正かが決まらないため。
    変更内容は :attr:`content` に記述する。
    """

    responded_by: PrescriberName
    responded_at: InquiryTimestamp
    result_type: InquiryResultType
    content: InquiryResponseContent

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "responded_by": "回答医師氏名",
        "responded_at": "回答日時",
        "result_type": "結果区分",
        "content": "回答内容",
    }

    @property
    def blocks_dispensing(self) -> bool:
        """この回答により当該処方の調剤ができなくなるか。"""
        return self.result_type.blocks_dispensing


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


@dataclass(frozen=True, kw_only=True)
class MedicineClassification(ValueObject):
    """医薬品マスタから受け取った、処方箋の判定に必要な事実。

    **これは医薬品マスタの生データではない。** ``is_refill_restricted_patch`` は
    「貼付剤であって鎮痛・消炎の効能を有し、麻薬・向精神薬でなく、専ら皮膚疾患に
    用いるものでもない」という**リフィルの規則が定める組み合わせ**であり、
    薬価基準の1カラムではない。導出は Composition のアダプタ（腐敗防止層）が行う。

    したがってこの型は Shared Kernel の共有語彙ではなく、**Prescription が
    Boundary から受け取る問い合わせ結果の形**である。
    """

    identifier: MedicineIdentifier
    #: 麻薬に該当するか（麻薬処方箋の必須3項目の判定に使う）。
    is_narcotic: MedicineRestrictionFlag = MedicineRestrictionFlag.UNKNOWN
    #: 投与量に限度が定められている医薬品か（リフィル適用除外の判定に使う）。
    has_dosage_limit: MedicineRestrictionFlag = MedicineRestrictionFlag.UNKNOWN
    #: リフィル不可の貼付剤か。
    #:
    #: 保険調剤の理解のために（令和8年度）の定義「鎮痛・消炎に係る効能及び効果を
    #: 有するものであって、麻薬若しくは向精神薬であるもの又は専ら皮膚疾患に
    #: 用いるものを除いたもの」を**適用済みの結果**を持つ。除外条件まで含めて
    #: マスタ側で判定させることで、「湿布薬は不可」のような誤った例示が
    #: ドメインへ入り込むのを防ぐ。
    is_refill_restricted_patch: MedicineRestrictionFlag = (
        MedicineRestrictionFlag.UNKNOWN
    )

    _FIELD_LABELS: ClassVar[dict[str, str]] = {
        "identifier": "薬品識別子",
        "is_narcotic": "麻薬区分",
        "has_dosage_limit": "投与量限度区分",
        "is_refill_restricted_patch": "貼付剤区分",
    }

    @property
    def has_unknown_flag(self) -> bool:
        """判定に必要な属性のいずれかが不明か。"""
        return any(
            flag.is_unknown
            for flag in (
                self.is_narcotic,
                self.has_dosage_limit,
                self.is_refill_restricted_patch,
            )
        )

    @property
    def forbids_refill(self) -> bool:
        """リフィル処方箋による調剤ができない医薬品か。

        「投与量に限度が定められている医薬品」**及び**「貼付剤」のいずれかに
        該当すれば不可。``UNKNOWN`` はここでは ``False`` を返すので、
        呼び出し側が先に ``has_unknown_flag`` を確認すること。
        """
        return (
            self.has_dosage_limit is MedicineRestrictionFlag.YES
            or self.is_refill_restricted_patch is MedicineRestrictionFlag.YES
        )
