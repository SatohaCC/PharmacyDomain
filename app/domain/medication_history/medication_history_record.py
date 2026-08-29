"""薬歴指導記録集約。

本コンテキストにおける**唯一の真実の源**。頭書き（``PatientMedicalProfile``）は
この集約の列から決定的に再構築できる投影であり、独立した真実を持たない。

**集約が単独で検証できることだけを ``validate()`` に置く。** 指導した薬剤師の
資格は Staff 集約が持ち、調剤セッションとの患者一致は Dispensing 集約が持つ。
これらは Domain Service が担う
（``okf/ddd/medication_history.md`` §5 の「守り手」列）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryNotFinalizedError,
    SoapSectionEmptyError,
)
from app.domain.medication_history.primitives import (
    AmendmentReason,
    AmendmentTimestamp,
    CounselingMethod,
    CounselingTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.value_objects import (
    HandbookStatus,
    MedicationHistoryAmendment,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryRecord(AggregateRoot[MedicationHistoryRecordId]):
    """1回の服薬指導の記録を管理する集約ルート。"""

    id: MedicationHistoryRecordId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    dispensing_id: DispensingId
    prescription_id: PrescriptionId
    counselor_id: StaffId
    counseled_at: CounselingTimestamp
    method: CounselingMethod
    soap: SoapRecord
    handbook_status: HandbookStatus
    #: 法定記載事項ウ（ホ）が「残薬がないときは、その旨を記載すること」と定めるため必須。
    residual_drug: ResidualDrugRecord
    information_sheet_provided: bool = False
    # 別モジュールの frozen dataclass なので ruff が不変性を追えない（RUF009）。
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    status: MedicationHistoryStatus = MedicationHistoryStatus.DRAFT
    amendments: tuple[MedicationHistoryAmendment, ...] = ()

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """薬歴が単独で判定できる不変条件を検証する。

        SOAP の充足（不変条件 #2）は**確定時にだけ**課す。下書きの途中で
        全セクションを要求すると、聞き取りながら書き足す運用ができない。
        """
        self._ensure_amendments_only_after_finalized()

    def _ensure_amendments_only_after_finalized(self) -> None:
        """追記が確定済の薬歴にだけ付くことを検証する。"""
        if self.amendments and not self.status.is_finalized:
            raise MedicationHistoryNotFinalizedError()

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        """確定済か。"""
        return self.status.is_finalized

    @property
    def effective_soap(self) -> SoapRecord:
        """現時点で有効なSOAP。追記があれば最後の追記の内容。

        元の記録を書き換えないので、``soap`` は交付時のまま残る。
        """
        if not self.amendments:
            return self.soap
        return self.amendments[-1].amended_soap

    @property
    def updates_profile(self) -> bool:
        """この薬歴が頭書きへ差分を持つか。"""
        return not self.profile_updates.is_empty

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
        dispensing_id: DispensingId,
        prescription_id: PrescriptionId,
        counselor_id: StaffId,
        counseled_at: CounselingTimestamp,
        method: CounselingMethod,
        soap: SoapRecord,
        handbook_status: HandbookStatus,
        residual_drug: ResidualDrugRecord,
        information_sheet_provided: bool = False,
        profile_updates: ProfileUpdateIntents | None = None,
    ) -> Self:
        """服薬指導の記録を下書きとして起こす。"""
        return cls(
            id=MedicationHistoryRecordId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            method=method,
            soap=soap,
            handbook_status=handbook_status,
            residual_drug=residual_drug,
            information_sheet_provided=information_sheet_provided,
            profile_updates=(
                profile_updates
                if profile_updates is not None
                else ProfileUpdateIntents()
            ),
            status=MedicationHistoryStatus.DRAFT,
        )

    # ------------------------------------------------------------------
    # 編集と確定
    # ------------------------------------------------------------------

    def update_draft_soap(self, soap: SoapRecord) -> Self:
        """下書きのSOAPを差し替える（不変条件 #7）。

        確定済の薬歴は受け付けない。修正は :meth:`amend` による追記のみ。
        """
        self._ensure_not_finalized()
        return replace(self, soap=soap)

    def update_draft_profile_updates(self, intents: ProfileUpdateIntents) -> Self:
        """下書きの頭書き差分を差し替える。"""
        self._ensure_not_finalized()
        return replace(self, profile_updates=intents)

    def finalize(self) -> Self:
        """薬歴を確定する（不変条件 #2）。

        SOAP の S / O / A / P のいずれかが空なら確定できない。通則(4) が
        服薬状況・体調変化・今後の留意点などを記載事項として求めているため。
        """
        self._ensure_not_finalized()
        empty_section = self.soap.empty_section_label
        if empty_section is not None:
            raise SoapSectionEmptyError(section_label=empty_section)
        return replace(self, status=MedicationHistoryStatus.FINALIZED)

    def amend(
        self,
        *,
        amended_soap: SoapRecord,
        reason: AmendmentReason,
        amended_by: StaffId,
        amended_at: AmendmentTimestamp,
    ) -> Self:
        """確定済の薬歴に修正を**追記**する。

        元の ``soap`` は書き換えない。調剤録は3年間の保存義務があり、
        遡って書き換えられる記録は監査に耐えない。
        """
        if not self.is_finalized:
            raise MedicationHistoryNotFinalizedError()
        amendment = MedicationHistoryAmendment(
            amended_soap=amended_soap,
            reason=reason,
            amended_by=amended_by,
            amended_at=amended_at,
        )
        return replace(self, amendments=(*self.amendments, amendment))

    def _ensure_not_finalized(self) -> None:
        """確定済でないことを保証する。"""
        if self.is_finalized:
            raise MedicationHistoryAlreadyFinalizedError()
