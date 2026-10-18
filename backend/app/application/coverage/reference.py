"""Coverageから患者をIDだけで参照する境界。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.primitives import CoverageAppliedOn
from app.domain.coverage.value_objects import CoverageSelection
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class PatientReferenceBoundary(Protocol):
    """患者エンティティを渡さず、患者IDの存在だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人内に患者が存在することを確認する。

        Raises:
            CoveragePatientNotFoundError: 患者が存在しない場合、および患者が
                別法人に所属している場合。他テナントのデータは存在を隠すため
                403ではなく404相当のこの例外へ揃える。``AuthorizationError``
                を送出すると他法人の患者IDの存在が呼び出し元へ漏れる。
        """
        ...


class StoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人内に店舗が存在することを確認する。"""
        ...


class CoverageSelectionBoundary(Protocol):
    """患者資格IDを検証して、保存可能な適用選択へ変換する境界。"""

    async def build_selection(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_on: CoverageAppliedOn,
    ) -> CoverageSelection:
        """指定された患者資格から有効な適用選択を構成する。"""
        ...


class CoverageValidityBoundary(Protocol):
    """記録済みの適用選択を資格台帳から再検証する境界。"""

    async def is_selection_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        selection: CoverageSelection,
        applied_on: CoverageAppliedOn,
    ) -> bool:
        """同じ資格IDから同じ固定値を再構築できる場合だけTrueを返す。"""
        ...
