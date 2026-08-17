"""Claim Applicationが依存する外部集約の参照境界。"""

from __future__ import annotations

from typing import Protocol

from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.claim.primitives import CoverageUsageTimestamp
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


class StoreReferenceBoundary(Protocol):
    """店舗集約を直接保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人に店舗が存在することを確認する。"""
        ...


class PatientReferenceBoundary(Protocol):
    """患者集約を直接保持せず、患者の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人に患者が存在することを確認する。"""
        ...


class CoverageSnapshotBoundary(Protocol):
    """選択された資格を請求側スナップショットへ変換する境界。"""

    async def build_snapshot(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_at: CoverageUsageTimestamp,
    ) -> CoverageSnapshot:
        """資格IDを検証し、適用日時点の請求用スナップショットを構成する。"""
        ...
