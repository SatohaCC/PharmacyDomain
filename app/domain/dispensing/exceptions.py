"""Dispensingドメインの業務例外。"""

from __future__ import annotations

from app.base.domain.exceptions import DomainError


class DispensingDomainError(DomainError):
    """Dispensingドメインの基底例外。"""

    default_message = "調剤ドメインでエラーが発生しました。"
    default_code = "DISPENSING_DOMAIN_ERROR"


# --------------------------------------------------------------------------
# 構造の整合性
# --------------------------------------------------------------------------


class DispensedRpRequiredError(DispensingDomainError):
    """調剤した剤（Rp）が1件も無い調剤セッションを構築しようとした場合の例外。"""

    default_message = "調剤セッションには調剤した剤（Rp）が1件以上必要です。"
    default_code = "DISPENSING_RP_REQUIRED"


class DispensedMedicineRequiredError(DispensingDomainError):
    """調剤した薬品が1件も無い剤（Rp）を構築しようとした場合の例外。"""

    default_message = "調剤した剤（Rp）には薬品が1件以上必要です。"
    default_code = "DISPENSING_MEDICINE_REQUIRED"


class DuplicatedDispensedRpNumberError(DispensingDomainError):
    """同一の調剤セッションに同じRP番号が複数現れた場合の例外。

    RP番号は処方箋の剤との対応キーなので、重複すると突合が壊れる。
    処方箋側の「1から連続」とは違い、調剤側は処方箋の一部だけを調剤しうる
    （分割調剤・減数調剤）ため連続性は要求しない。
    """

    default_message = "同一の調剤セッションに同じRP番号を複数指定できません。"
    default_code = "DISPENSING_RP_NUMBER_DUPLICATED"


class DuplicatedDispensedLineNumberError(DispensingDomainError):
    """同一の剤（Rp）に同じ薬品連番が複数現れた場合の例外。"""

    default_message = "同一の剤（Rp）に同じ薬品連番を複数指定できません。"
    default_code = "DISPENSING_MEDICINE_LINE_NUMBER_DUPLICATED"


class DuplicatedPreparationMethodError(DispensingDomainError):
    """同一薬品に同じ調製方法が複数指定された場合の例外。"""

    default_message = "同一薬品に同じ調製方法を複数指定できません。"
    default_code = "DISPENSING_PREPARATION_METHOD_DUPLICATED"


# --------------------------------------------------------------------------
# 分割調剤・リフィル
# --------------------------------------------------------------------------


class DispensingIterationOutOfRangeError(DispensingDomainError):
    """分割理由ごとの調剤回数の範囲を外れている場合の例外。

    後発医薬品の試用（注10）は「2回目の調剤を行った場合に限り」であり実質2分割、
    医師の分割指示（注11）は3回まで、長期保存の困難性等（注9）は上限の定めが
    無いが2回目以降にしか成立しない。
    """

    default_message = "分割理由に対して調剤回数が範囲外です。"
    default_code = "DISPENSING_ITERATION_OUT_OF_RANGE"

    def __init__(
        self,
        *,
        reason_label: str | None = None,
        iteration: int | None = None,
        allowed: str | None = None,
    ) -> None:
        """分割理由・回数・許容範囲を添えて例外を生成する。"""
        message = self.default_message
        if reason_label is not None:
            message = f"{message}分割理由: {reason_label}。"
        if iteration is not None:
            message = f"{message}指定された回数: {iteration}。"
        if allowed is not None:
            message = f"{message}許容範囲: {allowed}。"
        super().__init__(message)


class NextDispensingDateMismatchError(DispensingDomainError):
    """調剤終了区分と次回調剤予定日の有無が食い違う場合の例外。

    調剤編 ``リフィル処方箋情報レコード(521)`` は、調剤終了区分に ``2``（継続）を
    記録した場合に次回調剤予定日を記録すると定めている。継続なのに予定日が無い、
    終了なのに予定日がある、のどちらも送信できない記録になる。
    """

    default_message = (
        "調剤を継続する場合は次回調剤予定日が必要で、終了する場合は指定できません。"
    )
    default_code = "DISPENSING_NEXT_DATE_MISMATCH"


# --------------------------------------------------------------------------
# 変更調剤
# --------------------------------------------------------------------------


class QuantityAdjustmentInvalidError(DispensingDomainError):
    """減数調剤の数量が不正な場合の例外。

    減数調剤は「用法及び用量の変更は行わずに投与日数等を減らす調剤」であり、
    処方時の数量より少なく、かつ 0 より大きくなければならない。0 にするなら
    処方箋の事前照会・削除が必要で、減数調剤としては記録できない。
    """

    default_message = (
        "減数調剤の数量は、処方時の数量より少なく0より大きい必要があります。"
    )
    default_code = "DISPENSING_QUANTITY_ADJUSTMENT_INVALID"

    def __init__(
        self, *, prescribed: int | None = None, dispensed: int | None = None
    ) -> None:
        """処方時の数量と調剤数量を添えて例外を生成する。"""
        message = self.default_message
        if prescribed is not None and dispensed is not None:
            message = f"{message}処方時: {prescribed}、調剤: {dispensed}。"
        super().__init__(message)


class SubstitutionWithoutChangeError(DispensingDomainError):
    """変更前と変更後が同一の代替調剤を記録しようとした場合の例外。

    ``original_identifier`` / ``original_name`` が欠落しないことは、
    :class:`SubstitutionDetail` の必須フィールド
    なので**型が既に保証している**。欠落は構築時点で起こりえないため、
    定義だけで raise されない例外にしない（AGENTS.md）。

    実際に起こりうるのは「代替したことにしているが中身が同じ」であり、
    これは後発品調剤の実績集計と調剤録の差分表示を静かに壊す。
    """

    default_message = "代替調剤の変更前と変更後が同一です。"
    default_code = "DISPENSING_SUBSTITUTION_WITHOUT_CHANGE"

    def __init__(self, *, medicine_name: str | None = None) -> None:
        """対象の薬品名を添えて例外を生成する。"""
        message = self.default_message
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


class SubstitutionNotAllowedError(DispensingDomainError):
    """処方箋の変更制限に反する代替調剤を行おうとした場合の例外。

    薬剤師法第23条第2項（処方医の同意なき変更の禁止）に対応する。
    """

    default_message = "処方箋の変更制限により、この代替調剤は行えません。"
    default_code = "DISPENSING_SUBSTITUTION_NOT_ALLOWED"

    def __init__(
        self,
        *,
        medicine_name: str | None = None,
        restriction_label: str | None = None,
    ) -> None:
        """対象の薬品名と変更制限を添えて例外を生成する。"""
        message = self.default_message
        if restriction_label is not None:
            message = f"{message}処方箋の指示: {restriction_label}。"
        if medicine_name is not None:
            message = f"{message}対象の薬品: {medicine_name}。"
        super().__init__(message)


# --------------------------------------------------------------------------
# 担当者・状態遷移
# --------------------------------------------------------------------------


class SelfVerificationNotAllowedError(DispensingDomainError):
    """調剤者本人が最終鑑査を行おうとした場合の例外。

    調剤した本人と鑑査した本人がそれぞれ記録されていることを要求する
    （管理薬剤師による一括代行署名の禁止）。
    """

    default_message = "最終鑑査は調剤を行った薬剤師以外が行う必要があります。"
    default_code = "DISPENSING_SELF_VERIFICATION_NOT_ALLOWED"


class VerificationNotPassedError(DispensingDomainError):
    """最終鑑査に合格していない調剤セッションを完了しようとした場合の例外。"""

    default_message = "最終鑑査に合格していない調剤セッションは完了できません。"
    default_code = "DISPENSING_VERIFICATION_NOT_PASSED"


class DispensingStatusTransitionError(DispensingDomainError):
    """許可されていない状態遷移を行おうとした場合の例外。"""

    default_message = "調剤セッションの状態遷移が許可されていません。"
    default_code = "DISPENSING_STATUS_TRANSITION_INVALID"

    def __init__(
        self, *, current: str | None = None, target: str | None = None
    ) -> None:
        """現在の状態と遷移先を添えて例外を生成する。"""
        message = self.default_message
        if current is not None and target is not None:
            message = f"{message}現在: {current}、遷移先: {target}。"
        super().__init__(message)


class CancellationReasonMismatchError(DispensingDomainError):
    """中止理由の有無が中止状態と食い違う場合の例外。"""

    default_message = (
        "調剤中止のときは中止理由が必要で、中止していないときは指定できません。"
    )
    default_code = "DISPENSING_CANCELLATION_REASON_MISMATCH"


class DispensingAlreadyExistsError(DispensingDomainError):
    """同一処方箋に同じ調剤回数のセッションが既に存在する場合の例外。"""

    default_message = "この処方箋には同じ調剤回数のセッションが既に存在します。"
    default_code = "DISPENSING_ITERATION_ALREADY_EXISTS"

    def __init__(self, *, iteration: int | None = None) -> None:
        """重複した調剤回数を添えて例外を生成する。"""
        message = self.default_message
        if iteration is not None:
            message = f"{message}調剤回数: {iteration}。"
        super().__init__(message)


# --------------------------------------------------------------------------
# 処方箋・前回セッションとの整合（Domain Service が守る）
# --------------------------------------------------------------------------


class DispensedRpNotInPrescriptionError(DispensingDomainError):
    """処方箋に存在しない剤（Rp）を調剤しようとした場合の例外。

    処方箋の**すべて**の剤を調剤することは要求しない（分割調剤・減数調剤では
    一部だけを調剤しうる）。逆向きだけを拒否する。
    """

    default_message = "処方箋に存在しない剤（Rp）は調剤できません。"
    default_code = "DISPENSING_RP_NOT_IN_PRESCRIPTION"

    def __init__(self, *, rp_number: int | None = None) -> None:
        """対象のRP番号を添えて例外を生成する。"""
        message = self.default_message
        if rp_number is not None:
            message = f"{message}RP番号: {rp_number}。"
        super().__init__(message)


class DispensedMedicineNotInPrescriptionError(DispensingDomainError):
    """処方箋に存在しない薬品を調剤しようとした場合の例外。"""

    default_message = "処方箋に存在しない薬品は調剤できません。"
    default_code = "DISPENSING_MEDICINE_NOT_IN_PRESCRIPTION"

    def __init__(
        self, *, rp_number: int | None = None, line_number: int | None = None
    ) -> None:
        """対象のRP番号と薬品連番を添えて例外を生成する。"""
        message = self.default_message
        if rp_number is not None and line_number is not None:
            message = f"{message}RP番号: {rp_number}、薬品連番: {line_number}。"
        super().__init__(message)


class SplitInstructionMissingError(DispensingDomainError):
    """医師の分割指示による調剤なのに、処方箋に分割指示が無い場合の例外。"""

    default_message = (
        "医師の分割指示による調剤には、処方箋に分割指示が記載されている必要があります。"
    )
    default_code = "DISPENSING_SPLIT_INSTRUCTION_MISSING"


class IterationExceedsInstructionError(DispensingDomainError):
    """処方箋の指示を超える回数の調剤を行おうとした場合の例外。"""

    default_message = "処方箋の指示を超える回数の調剤はできません。"
    default_code = "DISPENSING_ITERATION_EXCEEDS_INSTRUCTION"

    def __init__(
        self,
        *,
        iteration: int | None = None,
        limit: int | None = None,
        instruction: str | None = None,
    ) -> None:
        """回数・上限・指示の種類を添えて例外を生成する。"""
        message = self.default_message
        if instruction is not None:
            message = f"{message}指示: {instruction}。"
        if iteration is not None and limit is not None:
            message = f"{message}指定された回数: {iteration}、上限: {limit}。"
        super().__init__(message)


class DispensingOutsidePrescriptionPeriodError(DispensingDomainError):
    """1回目の調剤日が処方箋の使用期間外である場合の例外。

    「1回目の調剤を行うことが可能な期間については、使用期間に記載されている日
    までとする」。2回目以降には使用期間を課さない。
    """

    default_message = "1回目の調剤日が処方箋の使用期間外です。"
    default_code = "DISPENSING_OUTSIDE_PRESCRIPTION_PERIOD"

    def __init__(
        self, *, dispensed_on: str | None = None, valid_to: str | None = None
    ) -> None:
        """調剤日と使用期限を添えて例外を生成する。"""
        message = self.default_message
        if dispensed_on is not None and valid_to is not None:
            message = f"{message}調剤日: {dispensed_on}、使用期限: {valid_to}。"
        super().__init__(message)


class PreviousDispensingUnknownError(DispensingDomainError):
    """2回目以降なのに前回の調剤セッションが渡されない場合の例外。

    各回は別の保険薬局で行われうるが、その場合も調剤の状況は情報提供を通じて
    渡される前提である。「分からないので通す」に倒すと、次回調剤予定日の判定が
    常に素通りする。
    """

    default_message = "2回目以降の調剤には、前回の調剤状況が必要です。"
    default_code = "DISPENSING_PREVIOUS_UNKNOWN"

    def __init__(self, *, iteration: int | None = None) -> None:
        """対象の調剤回数を添えて例外を生成する。"""
        message = self.default_message
        if iteration is not None:
            message = f"{message}調剤回数: {iteration}。"
        super().__init__(message)


class PreviousDispensingCompletedError(DispensingDomainError):
    """前回が調剤終了だったのに次の回を行おうとした場合の例外。"""

    default_message = "前回の調剤で終了しているため、次の回の調剤はできません。"
    default_code = "DISPENSING_PREVIOUS_COMPLETED"


class DispensingScheduleOutOfRangeError(DispensingDomainError):
    """調剤日が前回の次回調剤予定日から離れすぎている場合の例外。"""

    default_message = "調剤日が次回調剤予定日の許容範囲外です。"
    default_code = "DISPENSING_SCHEDULE_OUT_OF_RANGE"

    def __init__(
        self,
        *,
        dispensed_on: str | None = None,
        scheduled_on: str | None = None,
        tolerance_days: int | None = None,
    ) -> None:
        """調剤日・予定日・許容日数を添えて例外を生成する。"""
        message = self.default_message
        if dispensed_on is not None and scheduled_on is not None:
            message = (
                f"{message}調剤日: {dispensed_on}、次回調剤予定日: {scheduled_on}。"
            )
        if tolerance_days is not None:
            message = f"{message}許容範囲: 前後{tolerance_days}日。"
        super().__init__(message)


class DispensingPharmacistQualificationError(DispensingDomainError):
    """調剤者・鑑査者が薬剤師資格を持たない場合の例外。

    薬剤師法第19条は薬剤師でない者の調剤を禁じ、最終鑑査もまた薬剤師の業務である。
    疑義照会の実施者（薬剤師法第24条）とは根拠条文が異なるため、
    Prescription 側の同種の検証とは別の例外・別のサービスとして持つ。
    """

    default_message = "調剤と最終鑑査は薬剤師資格を持つスタッフだけが行えます。"
    default_code = "DISPENSING_PHARMACIST_REQUIRED"

    def __init__(self, *, role_label: str | None = None) -> None:
        """対象の役割（調剤者・鑑査者）を添えて例外を生成する。"""
        message = self.default_message
        if role_label is not None:
            message = f"{message}対象: {role_label}。"
        super().__init__(message)
