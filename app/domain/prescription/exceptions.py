"""Prescriptionドメインの業務例外。"""

from __future__ import annotations

from app.base.domain.exceptions import DomainError


class PrescriptionDomainError(DomainError):
    """Prescriptionドメインの基底例外。"""

    default_message = "処方箋ドメインでエラーが発生しました。"
    default_code = "PRESCRIPTION_DOMAIN_ERROR"


# --------------------------------------------------------------------------
# 構造の整合性
# --------------------------------------------------------------------------


class PrescriptionRpRequiredError(PrescriptionDomainError):
    """剤（Rp）が1件も無い処方箋を構築しようとした場合の例外。"""

    default_message = "処方箋には剤（Rp）が1件以上必要です。"
    default_code = "PRESCRIPTION_RP_REQUIRED"


class PrescriptionMedicineRequiredError(PrescriptionDomainError):
    """薬品が1件も無い剤（Rp）を構築しようとした場合の例外。"""

    default_message = "剤（Rp）には薬品が1件以上必要です。"
    default_code = "PRESCRIPTION_MEDICINE_REQUIRED"


class RpNumberSequenceError(PrescriptionDomainError):
    """RP番号が1から連続した昇順になっていない場合の例外。

    レセプト・調剤録・電子処方箋のいずれもRP番号で剤を突合するため、
    欠番や重複があると下流で剤の対応が取れなくなる。
    """

    default_message = "RP番号は1から連続した昇順で採番してください。"
    default_code = "PRESCRIPTION_RP_NUMBER_SEQUENCE_INVALID"

    def __init__(self, *, actual: tuple[int, ...] | None = None) -> None:
        """実際の採番を添えて例外を生成する。"""
        message = self.default_message
        if actual is not None:
            message = f"{message}実際の採番: {list(actual)}。"
        super().__init__(message)


class MedicineLineNumberSequenceError(PrescriptionDomainError):
    """RP内の薬品連番が1から連続した昇順になっていない場合の例外。"""

    default_message = "RP内の薬品連番は1から連続した昇順で採番してください。"
    default_code = "PRESCRIPTION_MEDICINE_LINE_NUMBER_SEQUENCE_INVALID"

    def __init__(
        self, *, rp_number: int | None = None, actual: tuple[int, ...] | None = None
    ) -> None:
        """対象のRP番号と実際の採番を添えて例外を生成する。"""
        message = self.default_message
        if rp_number is not None:
            message = f"{message}対象のRP番号: {rp_number}。"
        if actual is not None:
            message = f"{message}実際の採番: {list(actual)}。"
        super().__init__(message)


# --------------------------------------------------------------------------
# 期間・指示
# --------------------------------------------------------------------------


class PrescriptionPeriodInvertedError(PrescriptionDomainError):
    """使用期限が交付日より前になっている場合の例外。"""

    default_message = "処方箋の使用期限は交付日以降の日付で指定してください。"
    default_code = "PRESCRIPTION_PERIOD_INVERTED"


class SplitIterationOutOfRangeError(PrescriptionDomainError):
    """当該分割回が全分割回数を超えている場合の例外。"""

    default_message = "当該分割回は全分割回数以内で指定してください。"
    default_code = "PRESCRIPTION_SPLIT_ITERATION_OUT_OF_RANGE"

    def __init__(
        self, *, total: int | None = None, iteration: int | None = None
    ) -> None:
        """全分割回数と当該分割回を添えて例外を生成する。"""
        message = self.default_message
        if total is not None and iteration is not None:
            message = f"{message}全分割回数: {total}、当該分割回: {iteration}。"
        super().__init__(message)


class DepartmentCodeRequiredError(PrescriptionDomainError):
    """診療科コード種別とコードの有無が食い違う場合の例外。"""

    default_message = (
        "診療科コード種別が「診療科コード」のときは診療科コードが必要です。"
    )
    default_code = "PRESCRIPTION_DEPARTMENT_CODE_REQUIRED"


class DosageSupplementCodeRequiredError(PrescriptionDomainError):
    """コード種別に対して必要なコードが欠けている場合の例外。"""

    default_message = "指定されたコード種別にはコードが必要です。"
    default_code = "PRESCRIPTION_DOSAGE_SUPPLEMENT_CODE_REQUIRED"


class ApplicationSiteCodeRequiredError(PrescriptionDomainError):
    """用法補足区分が「JAMI部位」なのに外用部位コードが無い場合の例外。"""

    default_message = "用法補足区分が「JAMI部位」のときは外用部位コードが必要です。"
    default_code = "PRESCRIPTION_APPLICATION_SITE_CODE_REQUIRED"


class UnequalDosageTotalMismatchError(PrescriptionDomainError):
    """不均等服用の各回合計が薬品の1日量と一致しない場合の例外。"""

    default_message = "不均等服用の各回服用量の合計が薬品の1日量と一致しません。"
    default_code = "PRESCRIPTION_UNEQUAL_DOSAGE_TOTAL_MISMATCH"

    def __init__(
        self,
        message: str | None = None,
        *,
        total: object | None = None,
        daily_amount: object | None = None,
    ) -> None:
        """合計と1日量を添えて例外を生成する。"""
        resolved = message if message is not None else self.default_message
        if total is not None and daily_amount is not None:
            resolved = f"{resolved}合計: {total}、1日量: {daily_amount}。"
        super().__init__(resolved)


# --------------------------------------------------------------------------
# 薬品コード・補足の整合性
# --------------------------------------------------------------------------


class MedicineCodeTypeNotAllowedError(PrescriptionDomainError):
    """電子処方箋で使用できない薬品コード種別が指定された場合の例外。

    処方編 別表15 は ``1:コードなし`` を「未使用」、``3:厚生省コード`` と
    ``6:HOTコード`` を「使用しない」と定めている。紙処方箋（JAHIS）では
    使えるため、受領元形式と組み合わせて初めて判定できる。
    """

    default_message = (
        "電子処方箋では、この薬品コード種別を使用できません"
        "（レセプト電算・YJ・一般名のいずれかで指定してください）。"
    )
    default_code = "PRESCRIPTION_MEDICINE_CODE_TYPE_NOT_ALLOWED"

    def __init__(self, *, code_type_label: str | None = None) -> None:
        """指定されたコード種別名を添えて例外を生成する。"""
        message = self.default_message
        if code_type_label is not None:
            message = f"{message}指定された種別: {code_type_label}。"
        super().__init__(message)


class DuplicatedMedicineSupplementError(PrescriptionDomainError):
    """同一薬品に同じ薬品補足区分が複数指定された場合の例外。"""

    default_message = "同一薬品に同じ薬品補足区分を複数指定できません。"
    default_code = "PRESCRIPTION_MEDICINE_SUPPLEMENT_DUPLICATED"


class DuplicatedDosageSupplementError(PrescriptionDomainError):
    """同一の剤（Rp）に同じ用法補足区分が複数指定された場合の例外。"""

    default_message = "同一の剤（Rp）に同じ用法補足区分を複数指定できません。"
    default_code = "PRESCRIPTION_DOSAGE_SUPPLEMENT_DUPLICATED"


# --------------------------------------------------------------------------
# 疑義照会・状態遷移
# --------------------------------------------------------------------------


class InquiryNumberSequenceError(PrescriptionDomainError):
    """疑義照会の連番が1から連続した昇順になっていない場合の例外。"""

    default_message = "疑義照会の連番は1から連続した昇順で採番してください。"
    default_code = "PRESCRIPTION_INQUIRY_NUMBER_SEQUENCE_INVALID"


class InquiryNotFoundError(PrescriptionDomainError):
    """指定された連番の疑義照会が存在しない場合の例外。"""

    default_message = "指定された疑義照会が見つかりません。"
    default_code = "PRESCRIPTION_INQUIRY_NOT_FOUND"

    def __init__(self, *, inquiry_number: int | None = None) -> None:
        """対象の連番を添えて例外を生成する。"""
        message = self.default_message
        if inquiry_number is not None:
            message = f"{message}照会連番: {inquiry_number}。"
        super().__init__(message)


class InquiryAlreadyResolvedError(PrescriptionDomainError):
    """回答済みの疑義照会に再度回答しようとした場合の例外。"""

    default_message = "この疑義照会にはすでに回答が記録されています。"
    default_code = "PRESCRIPTION_INQUIRY_ALREADY_RESOLVED"


class OpenInquiryExistsError(PrescriptionDomainError):
    """未回答の疑義照会があるまま調剤可能へ進めようとした場合の例外。"""

    default_message = "未回答の疑義照会があるため、処方箋を調剤可能にできません。"
    default_code = "PRESCRIPTION_OPEN_INQUIRY_EXISTS"


class PrescriptionStatusTransitionError(PrescriptionDomainError):
    """許可されていない状態遷移を行おうとした場合の例外。"""

    default_message = "処方箋の状態遷移が許可されていません。"
    default_code = "PRESCRIPTION_STATUS_TRANSITION_INVALID"

    def __init__(
        self, *, current: str | None = None, target: str | None = None
    ) -> None:
        """現在の状態と遷移先を添えて例外を生成する。"""
        message = self.default_message
        if current is not None and target is not None:
            message = f"{message}現在: {current}、遷移先: {target}。"
        super().__init__(message)


class PrescriptionDocumentNumberAlreadyExistsError(PrescriptionDomainError):
    """同一法人内で電子処方箋の引換番号が重複した場合の例外。

    引換番号は電子処方箋管理サービスが発行する一意な番号なので、重複は
    二重取り込みを意味する。紙処方箋の番号は医療機関ごとの採番であり
    法人内で衝突しうるため、この例外の対象にしない。
    """

    default_message = "この引換番号の電子処方箋はすでに登録されています。"
    default_code = "PRESCRIPTION_DOCUMENT_NUMBER_ALREADY_EXISTS"

    def __init__(self, *, document_number: str | None = None) -> None:
        """重複した引換番号を添えて例外を生成する。"""
        message = self.default_message
        if document_number is not None:
            message = f"{message}引換番号: {document_number}。"
        super().__init__(message)


class MedicineClassificationUnknownError(PrescriptionDomainError):
    """医薬品マスタに属性が無く、規制の判定ができない場合の例外。

    「分からない」を「該当しない」に丸めると、麻薬処方箋の必須項目チェックや
    リフィル適用除外の判定が素通りする。判定できないことを明示的に失敗として
    扱う（fail-closed）。
    """

    default_message = (
        "医薬品の規制区分が判定できないため、処方箋の検証を完了できません。"
    )
    default_code = "PRESCRIPTION_MEDICINE_CLASSIFICATION_UNKNOWN"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


class MedicineClassificationMissingError(PrescriptionDomainError):
    """処方箋に含まれる薬品の分類が渡されていない場合の例外。

    Domain Service は本物の値だけで判定するため、必要な分類が揃わない状態で
    「問題なし」と答えてはならない。
    """

    default_message = "処方箋に含まれる薬品の規制区分が渡されていません。"
    default_code = "PRESCRIPTION_MEDICINE_CLASSIFICATION_MISSING"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


class NarcoticPrescriptionDetailsRequiredError(PrescriptionDomainError):
    """麻薬を含む処方箋に麻薬処方箋情報が無い場合の例外。

    麻薬及び向精神薬取締法により、麻薬処方箋には麻薬施用者免許番号・
    患者住所・患者電話番号の記載が必要になる。
    """

    default_message = (
        "麻薬を含む処方箋には、麻薬施用者免許番号・患者住所・患者電話番号が必要です。"
    )
    default_code = "PRESCRIPTION_NARCOTIC_DETAILS_REQUIRED"


class RefillNotAllowedError(PrescriptionDomainError):
    """リフィル指示を適用できない医薬品が含まれている場合の例外。

    保険調剤の理解のために（令和8年度）「投与量に限度が定められている医薬品
    及び貼付剤（鎮痛・消炎に係る効能及び効果を有するものであって、麻薬若しくは
    向精神薬であるもの又は専ら皮膚疾患に用いるものを除いたもの）については、
    リフィル処方箋による調剤を行うことはできない」。
    """

    default_message = (
        "リフィル処方箋による調剤ができない医薬品が含まれています"
        "（投与量に限度が定められている医薬品、または貼付剤）。"
    )
    default_code = "PRESCRIPTION_REFILL_NOT_ALLOWED"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


class InquiryPharmacistQualificationError(PrescriptionDomainError):
    """疑義照会の実施者が薬剤師資格を持たない場合の例外。

    薬剤師法第24条は疑義照会の主体を薬剤師と定めており、医療事務や調剤補助が
    実施者として記録されてはならない。
    """

    default_message = "疑義照会は薬剤師資格を持つスタッフだけが実施できます。"
    default_code = "PRESCRIPTION_INQUIRY_PHARMACIST_REQUIRED"


class PublicExpenseBurdenNotCoveredError(PrescriptionDomainError):
    """患者資格に存在しない公費枠へ負担を割り当てた場合の例外。

    裏付けの無い公費負担のまま調剤へ進むと、レセプト提出時に返戻される。
    """

    default_message = "患者資格に存在しない公費枠へ負担を割り当てています。"
    default_code = "PRESCRIPTION_PUBLIC_EXPENSE_BURDEN_NOT_COVERED"

    def __init__(
        self, *, medicine_name: str | None = None, burden_label: str | None = None
    ) -> None:
        """対象の薬品名と公費枠名を添えて例外を生成する。"""
        message = self.default_message
        if burden_label is not None:
            message = f"{message}対象の枠: {burden_label}。"
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)
