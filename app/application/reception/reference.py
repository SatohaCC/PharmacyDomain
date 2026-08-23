"""Reception Applicationが依存する参照境界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import CoverageAppliedOn, SourceCoverageId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class CoverageSelectionMaterial:
    """正規化済み元ID列とスナップショットを不可分に渡す境界DTO。"""

    source_coverage_ids: tuple[SourceCoverageId, ...]
    snapshot: CoverageSnapshot


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
    ) -> CoverageSelectionMaterial:
        """正規化済みID列と請求用スナップショットを構成する。

        Raises:
            ReceptionCoverageSelectionError: 資格の不在・別テナント・別患者・
                期間外または組み合わせ不成立の場合。存在は区別して漏らさない。
        """
        ...


class CoverageValidityBoundary(Protocol):
    """記録済みの元IDと値が適用日時点でも真正か再検証する境界。"""

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        source_coverage_ids: tuple[SourceCoverageId, ...],
        snapshot: CoverageSnapshot,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ元IDから同じ値を再構築できる場合だけTrueを返す。

        欠落・別テナント・別患者・期間外・無効化・値不一致はすべてFalseへ
        畳み、資格の存在を例外で区別しない。
        """
        ...
