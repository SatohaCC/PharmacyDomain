"""受付で確定した適用資格選択の履歴集約。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from app.base.domain.entity import AggregateRoot
from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception.exceptions import CoverageSelectionRecordInvalidError
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
    """患者・店舗単位で受付時の資格選択と監査情報を保存する。"""

    id: CoverageSelectionRecordId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    applied_on: CoverageAppliedOn
    source_coverage_ids: tuple[SourceCoverageId, ...]
    snapshot: CoverageSnapshot
    recorded_at: CoverageRecordedAt
    recorded_by: OperatorPrincipalId

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "適用資格選択履歴ID",
        "corporate_id": "法人ID",
        "store_id": "店舗ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "source_coverage_ids": "選択元患者資格ID",
        "snapshot": "資格スナップショット",
        "recorded_at": "記録時刻",
        "recorded_by": "記録者",
    }

    def validate(self) -> None:
        """元IDの件数・重複とスナップショット件数を照合する。"""
        if not self.source_coverage_ids:
            raise CoverageSelectionRecordInvalidError(
                "選択元患者資格IDを1件以上指定してください。"
            )
        if len(self.source_coverage_ids) != len(set(self.source_coverage_ids)):
            raise CoverageSelectionRecordInvalidError(
                "選択元患者資格IDは重複して指定できません。"
            )
        expected_count = (1 if self.snapshot.insurance is not None else 0) + len(
            self.snapshot.public_expenses
        )
        if len(self.source_coverage_ids) != expected_count:
            raise CoverageSelectionRecordInvalidError(
                "選択元患者資格IDとスナップショットの件数が一致しません。"
            )

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        applied_on: CoverageAppliedOn,
        source_coverage_ids: tuple[SourceCoverageId, ...],
        snapshot: CoverageSnapshot,
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
            source_coverage_ids=source_coverage_ids,
            snapshot=snapshot,
            recorded_at=recorded_at,
            recorded_by=recorded_by,
        )
