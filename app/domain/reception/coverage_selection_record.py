"""受付で確定した適用資格選択の履歴集約。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from app.base.domain.entity import AggregateRoot
from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.coverage_selection import CoverageSelection
from app.domain.reception.primitives import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelectionRecordId,
    OperatorPrincipalId,
    SourceCoverageId,
)
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class CoverageSelectionRecord(AggregateRoot[CoverageSelectionRecordId]):
    """患者・店舗単位で受付時の資格選択と監査情報を保存する。

    選択は :class:`CoverageSelection` 1つとして持つ。元資格IDと請求固定値を
    平坦な2フィールドへ分けると両者の対応が並び順の規約になってしまうため、
    枠がIDと値を束ねた形のまま保持する。``snapshot`` と ``source_coverage_ids``
    はその枠構造からの導出値であり、独立した記憶域を持たない。
    """

    id: CoverageSelectionRecordId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    applied_on: CoverageAppliedOn
    selection: CoverageSelection
    recorded_at: CoverageRecordedAt
    recorded_by: OperatorPrincipalId

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "適用資格選択履歴ID",
        "corporate_id": "法人ID",
        "store_id": "店舗ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "selection": "適用資格選択",
        "recorded_at": "記録時刻",
        "recorded_by": "記録者",
    }

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        applied_on: CoverageAppliedOn,
        selection: CoverageSelection,
        recorded_at: CoverageRecordedAt,
        recorded_by: OperatorPrincipalId,
    ) -> Self:
        """信頼済み監査値を含む適用資格選択履歴を生成する。"""
        return cls(
            id=CoverageSelectionRecordId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            applied_on=applied_on,
            selection=selection,
            recorded_at=recorded_at,
            recorded_by=recorded_by,
        )

    @property
    def snapshot(self) -> CoverageSnapshot:
        """請求へ渡す不変スナップショット。"""
        return self.selection.snapshot

    @property
    def source_coverage_ids(self) -> tuple[SourceCoverageId, ...]:
        """選択元IDを医療保険、公費順位順で返す。"""
        return self.selection.source_coverage_ids
