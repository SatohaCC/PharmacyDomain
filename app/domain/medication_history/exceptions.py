"""MedicationHistoryドメインの業務例外。"""

from __future__ import annotations

from app.base.domain.exceptions import DomainError


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
