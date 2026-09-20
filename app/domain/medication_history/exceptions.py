"""MedicationHistoryドメインの業務例外。"""

from __future__ import annotations

from app.domain.foundation.exceptions import DomainError


class MedicationHistoryDomainError(DomainError):
    """MedicationHistoryドメインの基底例外。"""

    default_message = "薬歴ドメインでエラーが発生しました。"
    default_code = "MEDICATION_HISTORY_DOMAIN_ERROR"


# --------------------------------------------------------------------------
# 法定記載事項
# --------------------------------------------------------------------------


class SoapSectionEmptyError(MedicationHistoryDomainError):
    """確定時にSOAPのいずれかのセクションが空の場合の例外。

    保険調剤の理解のために（令和8年度）第2節 通則(4) は、服薬状況・体調変化・
    今後の留意点などを記載事項として求めている。S/O/A/P のいずれかが空の薬歴は
    法定記載事項を満たさない。
    """

    default_message = "薬歴を確定するには、SOAPの各セクションに記載が必要です。"
    default_code = "MEDICATION_HISTORY_SOAP_SECTION_EMPTY"

    def __init__(self, *, section_label: str | None = None) -> None:
        """空だったセクション名を添えて例外を生成する。"""
        message = self.default_message
        if section_label is not None:
            message = f"{message}記載が無いセクション: {section_label}。"
        super().__init__(message)


class SoapContentRequiredError(MedicationHistoryDomainError):
    """薬歴確定時にSOAPおよび記録メモがすべて空（白紙）の場合の例外。"""

    default_message = (
        "確定済みの薬歴には服薬指導の記録が1件以上必要です（白紙では確定できません）。"
    )
    default_code = "MEDICATION_HISTORY_SOAP_CONTENT_REQUIRED"


class DuplicateMajorCategoryError(MedicationHistoryDomainError):
    """大区分コードが重複している場合の例外。"""

    default_message = "同一の区分カタログ内で大区分コードが重複しています。"
    default_code = "MEDICATION_HISTORY_DUPLICATE_MAJOR_CATEGORY"


class DuplicateMediumCategoryError(MedicationHistoryDomainError):
    """中区分コードが重複している場合の例外。"""

    default_message = "同一の区分カタログ内で中区分コードが重複しています。"
    default_code = "MEDICATION_HISTORY_DUPLICATE_MEDIUM_CATEGORY"


class MajorCategoryNotFoundError(MedicationHistoryDomainError):
    """中区分が参照する大区分が存在しない場合の例外。"""

    default_message = "指定された大区分コードは区分カタログに存在しません。"
    default_code = "MEDICATION_HISTORY_MAJOR_CATEGORY_NOT_FOUND"


class RequiredCategoryMissingError(MedicationHistoryDomainError):
    """法人ルールで必須と指定された中区分に記載がない場合の例外。"""

    default_message = "法人ルールで必須とされている中区分に記載がありません。"
    default_code = "MEDICATION_HISTORY_REQUIRED_CATEGORY_MISSING"

    def __init__(self, *, medium_category_name: str | None = None) -> None:
        message = self.default_message
        if medium_category_name is not None:
            message = f"{message}不足している中区分: {medium_category_name}。"
        super().__init__(message)


class ResidualDrugDetailRequiredError(MedicationHistoryDomainError):
    """残薬ありとしたのに数量または理由が無い場合の例外。

    法定記載事項ウ（ホ）は「残薬状況（残薬がないときは、その旨を記載すること）」を
    求めており、残薬がある場合はその内容が要る。
    """

    default_message = "残薬がある場合は、数量と発生理由の記載が必要です。"
    default_code = "MEDICATION_HISTORY_RESIDUAL_DRUG_DETAIL_REQUIRED"


class ResidualDrugDetailNotAllowedError(MedicationHistoryDomainError):
    """残薬なしとしたのに数量または理由が記録されている場合の例外。"""

    default_message = "残薬が無い場合は、数量と発生理由を指定できません。"
    default_code = "MEDICATION_HISTORY_RESIDUAL_DRUG_DETAIL_NOT_ALLOWED"


class HandbookGuidanceRequiredError(MedicationHistoryDomainError):
    """手帳を活用しなかったのに理由または指導の有無が無い場合の例外。

    法定記載事項ウ（ト）は「活用しなかった場合はその理由と患者への指導の有無」を
    求めている。
    """

    default_message = (
        "お薬手帳を活用しなかった場合は、その理由と患者への指導の有無が必要です。"
    )
    default_code = "MEDICATION_HISTORY_HANDBOOK_GUIDANCE_REQUIRED"


class HandbookReasonNotAllowedError(MedicationHistoryDomainError):
    """手帳を活用したのに未活用の理由が記録されている場合の例外。"""

    default_message = "お薬手帳を活用した場合は、未活用の理由を指定できません。"
    default_code = "MEDICATION_HISTORY_HANDBOOK_REASON_NOT_ALLOWED"


# --------------------------------------------------------------------------
# 併用薬・頭書き
# --------------------------------------------------------------------------


class ConcurrentMedicationPeriodInvertedError(MedicationHistoryDomainError):
    """併用薬の終了日が開始日より前になっている場合の例外。"""

    default_message = "併用薬の終了日は開始日以降の日付で指定してください。"
    default_code = "MEDICATION_HISTORY_CONCURRENT_PERIOD_INVERTED"


class ConcurrentMedicationNotFoundError(MedicationHistoryDomainError):
    """終了させようとした併用薬が頭書きに存在しない場合の例外。"""

    default_message = "指定された併用薬が頭書きに見つかりません。"
    default_code = "MEDICATION_HISTORY_CONCURRENT_NOT_FOUND"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


class AllergyNotFoundError(MedicationHistoryDomainError):
    """取り消そうとしたアレルギー歴が頭書きに存在しない場合の例外。"""

    default_message = "指定されたアレルギー歴が頭書きに見つかりません。"
    default_code = "MEDICATION_HISTORY_ALLERGY_NOT_FOUND"

    def __init__(self, *, allergen: str | None = None) -> None:
        """対象のアレルゲン名を添えて例外を生成する。"""
        message = self.default_message
        if allergen is not None:
            message = f"{message}対象のアレルゲン: {allergen}。"
        super().__init__(message)


class AdverseReactionNotFoundError(MedicationHistoryDomainError):
    """取り消そうとした副作用歴が頭書きに存在しない場合の例外。"""

    default_message = "指定された副作用歴が頭書きに見つかりません。"
    default_code = "MEDICATION_HISTORY_ADVERSE_REACTION_NOT_FOUND"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の医薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の医薬品: {medicine_name}。"
        super().__init__(message)


class MedicalConditionNotFoundError(MedicationHistoryDomainError):
    """更新または取り消そうとした疾患情報が頭書きに存在しない場合の例外。"""

    default_message = "指定された疾患情報が頭書きに見つかりません。"
    default_code = "MEDICATION_HISTORY_CONDITION_NOT_FOUND"

    def __init__(self, *, condition_name: str | None = None) -> None:
        """対象の疾患名を添えて例外を生成する。"""
        message = self.default_message
        if condition_name is not None:
            message = f"{message}対象の疾患: {condition_name}。"
        super().__init__(message)


class ProfilePatientMismatchError(MedicationHistoryDomainError):
    """別の患者・別法人の薬歴を頭書きへ投影しようとした場合の例外。

    投影は「その患者の薬歴を畳み込んだもの」であり、他患者の記録が混ざると
    再構築が成立しない。
    """

    default_message = "この頭書きには、別の患者・法人の薬歴を投影できません。"
    default_code = "MEDICATION_HISTORY_PROFILE_PATIENT_MISMATCH"


class UnfinalizedRecordProjectionError(MedicationHistoryDomainError):
    """未確定（下書き）の薬歴を頭書きへ投影しようとした場合の例外。

    下書きは以降も書き換わるため、投影の入力にすると再構築結果が安定しない。
    """

    default_message = "確定していない薬歴は頭書きへ投影できません。"
    default_code = "MEDICATION_HISTORY_UNFINALIZED_PROJECTION"


# --------------------------------------------------------------------------
# 状態遷移
# --------------------------------------------------------------------------


class MedicationHistoryAlreadyFinalizedError(MedicationHistoryDomainError):
    """確定済の薬歴を上書き編集しようとした場合の例外。

    調剤録は3年間の保存義務があり、遡って書き換えられる記録は監査に耐えない。
    修正は ``amend()`` による追記のみとする。
    """

    default_message = (
        "確定済の薬歴は上書きできません。修正は追記（amend）で行ってください。"
    )
    default_code = "MEDICATION_HISTORY_ALREADY_FINALIZED"


class MedicationHistoryNotFinalizedError(MedicationHistoryDomainError):
    """未確定の薬歴に追記しようとした場合の例外。"""

    default_message = "未確定の薬歴には追記できません。先に確定してください。"
    default_code = "MEDICATION_HISTORY_NOT_FINALIZED"


class MedicationHistoryAlreadyExistsError(MedicationHistoryDomainError):
    """同一調剤セッションに確定済の薬歴が既に存在する場合の例外。"""

    default_message = "この調剤には確定済の薬歴が既に存在します。"
    default_code = "MEDICATION_HISTORY_ALREADY_EXISTS"


class PatientMedicalProfileAlreadyExistsError(MedicationHistoryDomainError):
    """同一患者の頭書きが既に存在する場合の例外。"""

    default_message = "この患者の頭書きは既に存在します。"
    default_code = "MEDICATION_HISTORY_PROFILE_ALREADY_EXISTS"


class CounselorQualificationError(MedicationHistoryDomainError):
    """服薬指導を行った者が薬剤師資格を持たない場合の例外。

    薬剤師法第25条の2は情報の提供及び指導の義務を薬剤師に課している。
    """

    default_message = "服薬指導は薬剤師資格を持つスタッフだけが行えます。"
    default_code = "MEDICATION_HISTORY_COUNSELOR_QUALIFICATION_REQUIRED"


class StatutoryRecordSourceMismatchError(MedicationHistoryDomainError):
    """薬歴・調剤セッション・スナップショットが同じ1件を指していない場合の例外。

    無関係な記録を継ぎ接ぎした「充足」を作らせないため、報告ではなく拒否する。
    """

    default_message = (
        "調剤録の記載事項は、同じ調剤に対応する薬歴と記録からのみ判定できます。"
    )
    default_code = "MEDICATION_HISTORY_STATUTORY_SOURCE_MISMATCH"


class StatutoryItemNotAssessedError(MedicationHistoryDomainError):
    """調剤録の記載事項に判定の無いものが残っている場合の例外。

    記載事項を1つでも落とした結果は、調剤録の充足を語れない。
    """

    default_message = "判定していない調剤録の記載事項があります。"
    default_code = "MEDICATION_HISTORY_STATUTORY_ITEM_NOT_ASSESSED"

    def __init__(self, *, item_labels: tuple[str, ...] = ()) -> None:
        """判定の無かった記載事項名を添えて例外を生成する。"""
        message = self.default_message
        if item_labels:
            message = f"{message}判定が無い事項: {'、'.join(item_labels)}。"
        super().__init__(message)


class StatutoryItemAssessedTwiceError(MedicationHistoryDomainError):
    """同じ記載事項に2つ以上の判定が付いている場合の例外。

    どちらが答えかが決まらない結果を、充足の根拠として残さない。
    """

    default_message = "同じ調剤録の記載事項に複数の判定が付いています。"
    default_code = "MEDICATION_HISTORY_STATUTORY_ITEM_ASSESSED_TWICE"
