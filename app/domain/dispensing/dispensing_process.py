"""調剤セッション集約。

処方箋に対する1回ごとの調剤作業、変更調剤（代替調剤・数量調整・調製方法）、
および調剤鑑査の実績を管理する集約ルートです。

なお、集約単独で完結する整合性検証のみを ``validate()`` で実施し、
処方箋の指示範囲内であるか、代替調剤が処方箋の変更不可指示に反していないか、
調剤者・鑑査者が有資格者であるかといった複数集約に跨る検証は Domain Service が担当します。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.exceptions import (
    CancellationReasonMismatchError,
    DispensedMedicineRequiredError,
    DispensedRpRequiredError,
    DispensingDomainError,
    DispensingIterationOutOfRangeError,
    DispensingStatusTransitionError,
    DuplicatedDispensedLineNumberError,
    DuplicatedDispensedRpNumberError,
    DuplicatedPreparationMethodError,
    NextDispensingDateMismatchError,
    SubstitutionWithoutChangeError,
    TotalSplitCountMismatchError,
    VerificationNotPassedError,
    VerificationStatusMismatchError,
)
from app.domain.dispensing.primitives import (
    AuditNotes,
    AuditTimestamp,
    DispensedDate,
    DispensingCancellationReason,
    DispensingCompletionTimestamp,
    DispensingCompletionType,
    DispensingId,
    DispensingIteration,
    DispensingProcessStatus,
    DispensingSplitReason,
    DispensingTimestamp,
    NextDispensingDate,
    PreparationMethod,
    TotalSplitCount,
    VerificationNotes,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.dispensing.value_objects import (
    DispensingPrescriptionAudit,
    DispensingVerification,
    QuantityAdjustment,
    SubstitutionDetail,
)
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.shared.dosage import DosageInstruction
from app.domain.shared.medicine import (
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    RpNumber,
)
from app.domain.shared.preservation import (
    PreservationObligation,
    PreservationRecordKind,
    resolve_latest_retention_expiry_date,
)
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

#: ``status`` から遷移できる先。ここに無い組み合わせは拒否する。
_ALLOWED_TRANSITIONS: dict[
    DispensingProcessStatus, frozenset[DispensingProcessStatus]
] = {
    DispensingProcessStatus.IN_PROGRESS: frozenset(
        {
            # 鑑査不合格による再調製は状態を動かさないので、ここには現れない。
            DispensingProcessStatus.VERIFIED,
            DispensingProcessStatus.CANCELLED,
        }
    ),
    DispensingProcessStatus.VERIFIED: frozenset(
        {
            DispensingProcessStatus.COMPLETED,
            DispensingProcessStatus.CANCELLED,
        }
    ),
    DispensingProcessStatus.COMPLETED: frozenset(),
    DispensingProcessStatus.CANCELLED: frozenset(),
}

if set(_ALLOWED_TRANSITIONS) != set(DispensingProcessStatus):
    raise RuntimeError("DispensingProcessStatus の遷移表に定義漏れがあります。")


@dataclass(frozen=True, kw_only=True)
class DispensedMedicine(ValueObject):
    """調剤した医薬品の1明細。

    変更調剤の実績は以下の3つの観点に分かれます：
    1. 薬品自体の変更（代替調剤）: ``substitution``（本明細で保持）
    2. 調製方法の変更（一包化・粉砕等）: ``preparations``（本明細で保持）
    3. 数量の調整（減数調剤）: 剤単位で管理されるため :class:`DispensedRp` で保持
    """

    line_number: MedicineLineNumber
    identifier: MedicineIdentifier
    name: MedicineName
    amount: DosageAmount
    unit: MedicineUnit
    substitution: SubstitutionDetail | None = None
    preparations: tuple[PreparationMethod, ...] = ()
    public_expense_burden: PublicExpenseBurden | None = None

    def validate(self) -> None:
        """この明細だけで判定できる不変条件を検証する。"""
        self._ensure_substitution_describes_a_change()
        self._ensure_preparations_are_unique()

    def _ensure_substitution_describes_a_change(self) -> None:
        """代替調剤の変更前と変更後が同一でないことを検証する。"""
        if self.substitution is None:
            return
        if not self.substitution.describes_change_from(self.identifier, self.name):
            raise SubstitutionWithoutChangeError(medicine_name=self.name.value)

    def _ensure_preparations_are_unique(self) -> None:
        """同一の調製方法が重複して指定されていないことを検証する。

        一包化と粉砕のように「異なる」調製方法の組み合わせは正当ですが、
        同じ調製方法の重複指定は拒否します。
        """
        if len(self.preparations) != len(set(self.preparations)):
            raise DuplicatedPreparationMethodError()

    @property
    def is_substituted(self) -> bool:
        """処方原本から薬品そのものを置き換えたか。"""
        return self.substitution is not None


@dataclass(frozen=True, kw_only=True)
class DispensedRp(ValueObject):
    """調剤した剤（Rp）。処方箋の剤に ``rp_number`` で対応する。"""

    rp_number: RpNumber
    category: DosageFormCategory
    quantity: DispensingQuantity
    dosage_instruction: DosageInstruction
    medicines: tuple[DispensedMedicine, ...]
    quantity_adjustment: QuantityAdjustment | None = None

    def validate(self) -> None:
        """剤の構造的な不変条件を検証する。"""
        self._ensure_has_medicine()
        self._ensure_line_numbers_are_unique()
        self._ensure_quantity_adjustment_reduces()

    def _ensure_has_medicine(self) -> None:
        """薬品明細が1件以上あることを検証する。"""
        if not self.medicines:
            raise DispensedMedicineRequiredError()

    def _ensure_line_numbers_are_unique(self) -> None:
        """剤（RP）内の薬品明細連番が重複していないことを検証する。

        減数調剤や分割調剤において処方箋の一部の薬品のみを調剤する場合があるため、
        連番の欠番は許容されますが、重複は拒否します。
        """
        numbers = [medicine.line_number for medicine in self.medicines]
        if len(numbers) != len(set(numbers)):
            raise DuplicatedDispensedLineNumberError()

    def _ensure_quantity_adjustment_reduces(self) -> None:
        """減数調剤なら、実際の数量が処方時より少ないことを検証する。"""
        if self.quantity_adjustment is None:
            return
        self.quantity_adjustment.ensure_reduces(self.quantity)

    @property
    def is_quantity_adjusted(self) -> bool:
        """減数調剤を行ったか。"""
        return self.quantity_adjustment is not None

    @property
    def has_substitution(self) -> bool:
        """この剤に代替調剤を行った薬品が含まれるか。"""
        return any(medicine.is_substituted for medicine in self.medicines)


@dataclass(frozen=True, eq=False, kw_only=True)
class DispensingProcess(AggregateRoot[DispensingId]):
    """1回分の調剤セッションを管理する集約ルート。"""

    id: DispensingId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    prescription_id: PrescriptionId
    iteration: DispensingIteration
    dispensed_date: DispensedDate
    dispenser_id: StaffId
    started_at: DispensingTimestamp
    dispensed_rps: tuple[DispensedRp, ...]
    completion_type: DispensingCompletionType = DispensingCompletionType.COMPLETED
    split_reason: DispensingSplitReason | None = None
    total_split_count: TotalSplitCount | None = None
    next_dispensing_date: NextDispensingDate | None = None
    audit: DispensingPrescriptionAudit | None = None
    verification: DispensingVerification | None = None
    status: DispensingProcessStatus = DispensingProcessStatus.IN_PROGRESS
    cancellation_reason: DispensingCancellationReason | None = None
    completed_at: DispensingCompletionTimestamp | None = None
    completed_on: date | None = None

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """調剤セッションが単独で判定できる不変条件を検証する。"""
        self._ensure_has_rp()
        self._ensure_rp_numbers_are_unique()
        self._ensure_split_parameters_consistency()
        self._ensure_next_dispensing_date_matches_completion_type()
        self._ensure_cancellation_reason_matches_status()
        self._ensure_verification_matches_status()

    def _ensure_verification_matches_status(self) -> None:
        """状態が示す鑑査結果を構築・復元のどちらでも保証する。

        取消は鑑査の前後どちらでも起こるため、取消前の記録をそのまま保持する。
        """
        if self.status is DispensingProcessStatus.CANCELLED:
            return
        requires_passed = self.status in (
            DispensingProcessStatus.VERIFIED,
            DispensingProcessStatus.COMPLETED,
        )
        if self.is_verified != requires_passed:
            raise VerificationStatusMismatchError()

    def _ensure_has_rp(self) -> None:
        """調剤した剤（Rp）が1件以上あることを検証する。"""
        if not self.dispensed_rps:
            raise DispensedRpRequiredError()

    def _ensure_rp_numbers_are_unique(self) -> None:
        """RP番号が重複していないことを検証する。

        処方箋の剤と対応付けるキーであるため、重複は拒否します。
        分割調剤等で一部の剤のみを調剤する場合があるため、番号の連続性は強制しません。
        """
        numbers = [rp.rp_number for rp in self.dispensed_rps]
        if len(numbers) != len(set(numbers)):
            raise DuplicatedDispensedRpNumberError()

    def _ensure_split_parameters_consistency(self) -> None:
        """分割調剤パラメータ（分割理由・合計分割回数）の自己無撞着性を検証する。

        分割調剤の可否判定や点数算定はレセコンの責務であり、本集約では連携された事実を客観的に記録します。
        ここでは、パラメータの有無の整合性および「今回の調剤回数が合計分割回数以下であること」のみを保証します。
        """
        has_reason = self.split_reason is not None
        has_total = self.total_split_count is not None
        if has_reason != has_total:
            raise TotalSplitCountMismatchError()
        if (
            self.split_reason is not None
            and self.total_split_count is not None
            and self.iteration.value > self.total_split_count.value
        ):
            raise DispensingIterationOutOfRangeError(
                iteration=self.iteration.value,
                total=self.total_split_count.value,
            )

    def _ensure_next_dispensing_date_matches_completion_type(self) -> None:
        """調剤終了区分と次回調剤予定日の有無の整合性を検証する。

        次回以降の調剤が残っている場合（継続）にのみ次回予定日を設定し、
        完了または中止の場合は予定日が存在しないことを保証します。
        """
        has_next_date = self.next_dispensing_date is not None
        if has_next_date != self.completion_type.requires_next_date:
            raise NextDispensingDateMismatchError()

    def _ensure_cancellation_reason_matches_status(self) -> None:
        """調剤中止理由と調剤状態（CANCELLED）の整合性を検証する。"""
        has_reason = self.cancellation_reason is not None
        is_cancelled = self.status is DispensingProcessStatus.CANCELLED
        if has_reason != is_cancelled:
            raise CancellationReasonMismatchError()

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def is_verified(self) -> bool:
        """最終鑑査に合格しているか。"""
        return self.verification is not None and self.verification.is_passed

    @property
    def is_first_iteration(self) -> bool:
        """1回目の調剤か。処方箋の使用期間内かを判定する対象になる。"""
        return self.iteration.value == 1

    @property
    def continues(self) -> bool:
        """次回以降の調剤が残っているか。"""
        return self.completion_type is DispensingCompletionType.CONTINUES

    @property
    def dispensed_rp_numbers(self) -> tuple[RpNumber, ...]:
        """調剤した剤のRP番号（処方箋との突合に使う）。"""
        return tuple(rp.rp_number for rp in self.dispensed_rps)

    @property
    def substituted_medicines(self) -> tuple[DispensedMedicine, ...]:
        """代替調剤を行った薬品明細（変更制限との照合に使う）。"""
        return tuple(
            medicine
            for rp in self.dispensed_rps
            for medicine in rp.medicines
            if medicine.is_substituted
        )

    def find_rp(self, rp_number: RpNumber) -> DispensedRp | None:
        """指定のRP番号の剤を返す。無ければ ``None``。"""
        for rp in self.dispensed_rps:
            if rp.rp_number == rp_number:
                return rp
        return None

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        prescription_id: PrescriptionId,
        iteration: DispensingIteration,
        dispensed_date: DispensedDate,
        dispenser_id: StaffId,
        started_at: DispensingTimestamp,
        dispensed_rps: tuple[DispensedRp, ...],
        split_reason: DispensingSplitReason | None = None,
        total_split_count: TotalSplitCount | None = None,
    ) -> Self:
        """調剤セッションを開始する。

        調剤終了区分は完了時に決まるので、開始時は既定値
        （``COMPLETED``＝次回なし）で構築し、``complete()`` で確定させる。
        """
        return cls(
            id=DispensingId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            prescription_id=prescription_id,
            iteration=iteration,
            dispensed_date=dispensed_date,
            dispenser_id=dispenser_id,
            started_at=started_at,
            dispensed_rps=dispensed_rps,
            split_reason=split_reason,
            total_split_count=total_split_count,
            status=DispensingProcessStatus.IN_PROGRESS,
        )

    # ------------------------------------------------------------------
    # 記録
    # ------------------------------------------------------------------

    def record_audit(
        self,
        *,
        auditor_id: StaffId,
        audited_at: AuditTimestamp,
        has_issues: bool,
        notes: AuditNotes | None = None,
    ) -> Self:
        """処方鑑査の結果を記録する（調剤調製の前）。"""
        self._ensure_in_progress("処方鑑査の記録")
        return replace(
            self,
            audit=DispensingPrescriptionAudit(
                auditor_id=auditor_id,
                audited_at=audited_at,
                has_issues=has_issues,
                notes=notes,
            ),
        )

    def update_dispensed_rps(self, dispensed_rps: tuple[DispensedRp, ...]) -> Self:
        """調剤内容（代替調剤・数量・調製方法など）を更新する。

        鑑査で不合格となった後の再調製などもこのメソッドで行います。
        """
        self._ensure_in_progress("調剤内容の変更")
        return replace(self, dispensed_rps=dispensed_rps)

    def verify(
        self,
        *,
        verifier_id: StaffId,
        verified_at: VerificationTimestamp,
        result: VerificationResult,
        notes: VerificationNotes | None = None,
    ) -> Self:
        """調剤鑑査の結果を記録する。

        不合格（NG）の場合は調剤進行中（IN_PROGRESS）のまま維持し、
        再調製を行わずに交付完了へ進めないよう保護します。
        """
        self._ensure_in_progress("最終鑑査")
        verification = DispensingVerification(
            verifier_id=verifier_id,
            verified_at=verified_at,
            result=result,
            notes=notes,
        )
        status = self.status
        if result.is_passed:
            self._ensure_can_transition(DispensingProcessStatus.VERIFIED)
            status = DispensingProcessStatus.VERIFIED
        return replace(self, verification=verification, status=status)

    # ------------------------------------------------------------------
    # 状態遷移
    # ------------------------------------------------------------------

    def complete(
        self,
        *,
        completion_type: DispensingCompletionType,
        next_dispensing_date: NextDispensingDate | None = None,
        completed_at: DispensingCompletionTimestamp | None = None,
        completed_on: date | None = None,
    ) -> Self:
        """患者へ交付し、調剤セッションを完了する。

        ``completion_type`` は「総使用回数に達したか」だけでは決まらない。
        規格は「達していないが次回以降の調剤が不要となった場合」も終了として
        扱うため、判断は呼び出し側から渡される。
        """
        if not self.is_verified:
            raise VerificationNotPassedError()
        self._ensure_can_transition(DispensingProcessStatus.COMPLETED)
        if (completed_at is None) != (completed_on is None):
            raise DispensingDomainError(
                "調剤完了日時と完了業務日は両方指定してください。"
            )
        return replace(
            self,
            status=DispensingProcessStatus.COMPLETED,
            completion_type=completion_type,
            next_dispensing_date=next_dispensing_date,
            completed_at=completed_at,
            completed_on=completed_on,
        )

    def cancel(self, reason: DispensingCancellationReason) -> Self:
        """調剤を中止する。交付前であれば鑑査済からでも中止できる。

        理由は必須。中止したという事実だけを残すと、調剤録の記載としても
        患者への説明としても後から再現できない。
        """
        self._ensure_can_transition(DispensingProcessStatus.CANCELLED)
        return replace(
            self,
            status=DispensingProcessStatus.CANCELLED,
            cancellation_reason=reason,
        )

    def _ensure_can_transition(self, target: DispensingProcessStatus) -> None:
        """遷移表に載っている遷移であることを保証する。

        状態と同時に別のフィールドを埋める操作（中止理由・調剤終了区分）は、
        判定と ``replace`` を分けて**1回の再構築**にまとめる。2段階に分けると
        途中の状態が不変条件を満たさず、構築時検証で落ちる。
        """
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise DispensingStatusTransitionError(
                current=self.status.label, target=target.label
            )

    def _ensure_in_progress(self, operation: str) -> None:
        """調剤調製中にのみ許される操作であることを保証する。"""
        if self.status is not DispensingProcessStatus.IN_PROGRESS:
            raise DispensingStatusTransitionError(
                current=self.status.label, target=operation
            )

    def calculate_retention_expiry_date(
        self,
        obligation: PreservationObligation,
        *additional_obligations: PreservationObligation,
    ) -> date:
        """調剤録の法定保存満了日を計算する。

        薬剤師法第28条（調剤録の保存）等に基づき、完了操作で記録した業務日を
        最終記入日としてポリシーカタログから満了日を計算する。
        各義務には個別の起算日（(catalog, anchor_date) のタプル）を指定することもできる。
        複数のポリシーカタログが指定された場合は、各義務で計算した満了日のうち
        最も遅い日（最新満了日）を返す。
        """
        if self.completed_on is None:
            raise DispensingDomainError(
                "調剤録の保存満了日を計算するには完了業務日が必要です。"
            )
        return resolve_latest_retention_expiry_date(
            self.completed_on,
            PreservationRecordKind.DISPENSING_RECORD,
            obligation,
            *additional_obligations,
        )
