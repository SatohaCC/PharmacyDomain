"""調剤セッション集約。

1枚の処方箋に対する**1回ごと**の調剤作業・変更調剤・最終鑑査を管理する
整合性境界のルート。

**集約が単独で検証できることだけを ``validate()`` に置く。** 処方箋の指示の
範囲内か、前回セッションの次回予定日から前後7日以内か、代替調剤が処方箋の
変更制限に反しないか、調剤者・鑑査者が薬剤師かは、いずれも他の集約を見ないと
判定できない。これらは Domain Service が担う。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.base.domain.dosage import DosageInstruction
from app.base.domain.entity import AggregateRoot
from app.base.domain.medicine import (
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PublicExpenseBurden,
    RpNumber,
)
from app.base.domain.value_object import ValueObject
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.exceptions import (
    CancellationReasonMismatchError,
    DispensedMedicineRequiredError,
    DispensedRpRequiredError,
    DispensingIterationOutOfRangeError,
    DispensingStatusTransitionError,
    DuplicatedDispensedLineNumberError,
    DuplicatedDispensedRpNumberError,
    DuplicatedPreparationMethodError,
    NextDispensingDateMismatchError,
    SelfVerificationNotAllowedError,
    SubstitutionWithoutChangeError,
    VerificationNotPassedError,
)
from app.domain.dispensing.primitives import (
    AuditNotes,
    AuditTimestamp,
    DispensedDate,
    DispensingCancellationReason,
    DispensingCompletionType,
    DispensingId,
    DispensingIteration,
    DispensingProcessStatus,
    DispensingSplitReason,
    DispensingTimestamp,
    NextDispensingDate,
    PreparationMethod,
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
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
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
    """調剤した薬品の1明細。

    変更調剤は3軸に分かれる。``substitution``（何を出したか）と
    ``preparations``（どう加工したか）はこの明細が持ち、
    ``quantity_adjustment``（どれだけ出したか）は数量が剤単位のフィールドで
    あるため :class:`DispensedRp` が持つ。
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
        """同じ調製方法が重複していないことを検証する。

        一包化と粉砕のような**異なる**方法の同時成立は正当なので排他にしない
        （加算の排他は Claim の責務）。同じ方法の重複だけを拒否する。
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
        """RP内の薬品連番が重複していないことを検証する。

        処方箋側と違い連続性は要求しない。減数調剤や分割調剤では処方箋の
        一部の薬品だけを調剤しうるため、欠番は正当な記録になる。
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
    next_dispensing_date: NextDispensingDate | None = None
    audit: DispensingPrescriptionAudit | None = None
    verification: DispensingVerification | None = None
    status: DispensingProcessStatus = DispensingProcessStatus.IN_PROGRESS
    cancellation_reason: DispensingCancellationReason | None = None

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """調剤セッションが単独で判定できる不変条件を検証する。"""
        self._ensure_has_rp()
        self._ensure_rp_numbers_are_unique()
        self._ensure_iteration_matches_split_reason()
        self._ensure_next_dispensing_date_matches_completion_type()
        self._ensure_verifier_is_not_dispenser()
        self._ensure_cancellation_reason_matches_status()

    def _ensure_has_rp(self) -> None:
        """調剤した剤（Rp）が1件以上あることを検証する。"""
        if not self.dispensed_rps:
            raise DispensedRpRequiredError()

    def _ensure_rp_numbers_are_unique(self) -> None:
        """RP番号が重複していないことを検証する。

        処方箋の剤との対応キーなので、重複すると突合が壊れる。連続性は
        要求しない（分割調剤では処方箋の一部の剤だけを調剤しうる）。
        処方箋側に実在する番号かは Domain Service が判定する。
        """
        numbers = [rp.rp_number for rp in self.dispensed_rps]
        if len(numbers) != len(set(numbers)):
            raise DuplicatedDispensedRpNumberError()

    def _ensure_iteration_matches_split_reason(self) -> None:
        """分割理由ごとの調剤回数の範囲に収まっていることを検証する。

        リフィル処方箋の総使用回数は処方箋集約が持つので、ここでは判定せず
        Domain Service に委ねる。
        """
        if self.split_reason is None:
            return
        if not self.split_reason.allows_iteration(self.iteration.value):
            raise DispensingIterationOutOfRangeError(
                reason_label=self.split_reason.label,
                iteration=self.iteration.value,
                allowed=self.split_reason.allowed_range_label,
            )

    def _ensure_next_dispensing_date_matches_completion_type(self) -> None:
        """調剤終了区分と次回調剤予定日の有無が一致することを検証する。

        調剤編 ``リフィル処方箋情報レコード(521)`` は継続のときだけ予定日を
        記録すると定めている。片方だけの状態は送信できない記録になる。
        """
        has_next_date = self.next_dispensing_date is not None
        if has_next_date != self.completion_type.requires_next_date:
            raise NextDispensingDateMismatchError()

    def _ensure_cancellation_reason_matches_status(self) -> None:
        """中止理由の有無が中止状態と一致することを検証する。

        理由の無い中止は調剤録として意味を持たず、中止していないのに理由が
        残っている状態は前の中止操作の取り消し漏れを意味する。
        """
        has_reason = self.cancellation_reason is not None
        is_cancelled = self.status is DispensingProcessStatus.CANCELLED
        if has_reason != is_cancelled:
            raise CancellationReasonMismatchError()

    def _ensure_verifier_is_not_dispenser(self) -> None:
        """調剤者と最終鑑査者が別人であることを検証する。

        管理薬剤師による一括代行署名を防ぐ。両者が薬剤師資格を持つかは
        Staff 集約を見ないと判定できないので、ここでは同一性だけを見る。
        """
        if self.verification is None:
            return
        if self.verification.verifier_id == self.dispenser_id:
            raise SelfVerificationNotAllowedError()

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
        """調剤内容（変更調剤の3軸を含む）を差し替える。

        鑑査不合格による再調製もこの操作で行う。処方箋の変更制限に反する
        代替が含まれていないかは Domain Service が判定する。
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
        """最終鑑査の結果を記録する。

        不合格のときは状態を進めない。再調製のために ``IN_PROGRESS`` のまま
        にすることで、「不合格なのに交付できる」状態を作らない。
        """
        self._ensure_in_progress("最終鑑査")
        verification = DispensingVerification(
            verifier_id=verifier_id,
            verified_at=verified_at,
            result=result,
            notes=notes,
        )
        verified = replace(self, verification=verification)
        if not result.is_passed:
            return verified
        return verified._transition_to(DispensingProcessStatus.VERIFIED)

    # ------------------------------------------------------------------
    # 状態遷移
    # ------------------------------------------------------------------

    def complete(
        self,
        *,
        completion_type: DispensingCompletionType,
        next_dispensing_date: NextDispensingDate | None = None,
    ) -> Self:
        """患者へ交付し、調剤セッションを完了する。

        ``completion_type`` は「総使用回数に達したか」だけでは決まらない。
        規格は「達していないが次回以降の調剤が不要となった場合」も終了として
        扱うため、判断は呼び出し側から渡される。
        """
        if not self.is_verified:
            raise VerificationNotPassedError()
        self._ensure_can_transition(DispensingProcessStatus.COMPLETED)
        return replace(
            self,
            status=DispensingProcessStatus.COMPLETED,
            completion_type=completion_type,
            next_dispensing_date=next_dispensing_date,
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

    def _transition_to(self, target: DispensingProcessStatus) -> Self:
        """遷移表に従って状態を変更する。"""
        self._ensure_can_transition(target)
        return replace(self, status=target)

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
