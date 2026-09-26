"""Reception Applicationが依存する参照境界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.coverage_selection import CoverageSelection
from app.domain.reception.primitives import CoverageAppliedOn
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryAssociationReference:
    """受付との関連確認に必要な薬歴の識別情報。"""

    id: MedicationHistoryRecordId
    patient_id: PatientId
    dispensing_id: DispensingId
    prescription_id: PrescriptionId


class MedicationHistoryAssociationBoundary(Protocol):
    """薬歴集約を保持せず、受付との関連に必要な識別情報を返す境界。"""

    async def get_for_association(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryAssociationReference | None:
        """法人境界を適用し、指定薬歴の関連確認用情報を返す。"""
        ...


class StoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人に店舗が存在することを確認する。

        Raises:
            ReceptionStoreNotFoundError: 未存在または別法人の店舗である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class PatientReferenceBoundary(Protocol):
    """患者集約を保持せず、患者の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人に患者が存在することを確認する。

        Raises:
            ReceptionPatientNotFoundError: 未存在または別法人の患者である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class CoverageSelectionBoundary(Protocol):
    """患者資格IDを検証して受付で保存する値へ変換する境界。"""

    async def build_selection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelection:
        """元資格IDと請求固定値を枠ごとに束ねた選択を構成する。

        Raises:
            ReceptionCoverageSelectionError: 資格の不在・別テナント・別患者・
                期間外または組み合わせ不成立の場合。存在は区別して漏らさない。
                Domain側の ``CoverageSelectionInvalidError`` /
                ``CoverageCombinationInvalidError`` もここへ畳み込む。
        """
        ...


class CoverageValidityBoundary(Protocol):
    """記録済みの元IDと値が適用日時点でも真正か再検証する境界。"""

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        selection: CoverageSelection,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ元IDから同じ選択を再構築できる場合だけTrueを返す。

        欠落・別テナント・別患者・期間外・無効化・値不一致はすべてFalseへ
        畳み、資格の存在を例外で区別しない。枠ごとIDと値が束ねられているので、
        照合は再構築した ``CoverageSelection`` との等価比較1本で済む。
        """
        ...
