"""coverageのエンティティと集約。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import ClassVar, Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.exceptions import (
    CoverageDeactivationAlreadyFixedError,
    CoverageDetailsMismatchError,
    InsuranceCoveragePriorityError,
)
from app.domain.coverage.identifiers import CoverageSelectionRecordId, PatientCoverageId
from app.domain.coverage.primitives import (
    CoverageAppliedOn,
    CoverageDeactivatedOn,
    CoveragePriority,
    CoverageRecordedAt,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    OperatorPrincipalId,
)
from app.domain.coverage.value_objects import (
    CoverageActivation,
    CoveragePeriod,
    CoverageSelection,
    CoverageSnapshot,
    InsuranceCoverageDetails,
    PublicExpenseCoverageDetails,
)
from app.domain.foundation.entity import AggregateRoot
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, eq=False, kw_only=True)
class CoverageSelectionRecord(AggregateRoot[CoverageSelectionRecordId]):
    """患者・店舗単位で適用資格の選択と監査情報を保存する。

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

    @property
    def snapshot(self) -> CoverageSnapshot:
        """適用時点の不変スナップショット。"""
        return self.selection.snapshot

    @property
    def source_coverage_ids(self) -> tuple[PatientCoverageId, ...]:
        """選択元IDを医療保険、公費順位順で返す。"""
        return self.selection.source_coverage_ids


_NONE_TYPE = type(None)


@dataclass(frozen=True, eq=False, kw_only=True)
class PatientCoverage(AggregateRoot[PatientCoverageId]):
    """患者の健康保険証または公費医療の受給資格情報を管理するドメインエンティティ。"""

    id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    coverage_type: CoverageType
    period: CoveragePeriod
    activation: CoverageActivation
    priority: CoveragePriority
    insurance_details: InsuranceCoverageDetails | None = None
    public_expense_details: PublicExpenseCoverageDetails | None = None

    def validate(self) -> None:
        """保険種別（社保・国保・後期高齢者等）または公費負担医療（難病・自立支援等）の内容と設定の整合性を検証する。"""
        insurance_type, public_expense_type = _DETAIL_TYPES[self.coverage_type]
        if not isinstance(self.insurance_details, insurance_type) or not isinstance(
            self.public_expense_details, public_expense_type
        ):
            raise CoverageDetailsMismatchError()
        if self.coverage_type is CoverageType.INSURANCE and self.priority.value != 1:
            raise InsuranceCoveragePriorityError()

    def change_period(self, period: CoveragePeriod) -> Self:
        """保険証や公費受給者証の有効期間を変更する。"""
        return replace(self, period=period)

    def is_active_on(self, target_date: date) -> bool:
        """指定された日付（調剤日・受付日）において、保険証・受給者証の有効期間内であり、かつ台帳上で有効化されているかを判定する。"""
        if not self.activation.is_active_on(target_date):
            return False
        if target_date < self.period.valid_from.value:
            return False
        return self.period.valid_to is None or target_date <= self.period.valid_to.value

    def effective_period(self) -> CoveragePeriod | None:
        """制度期間と有効化区間が交差する実効期間を返す。"""
        effective_start = max(
            self.period.valid_from.value,
            self.activation.activated_on.value,
        )
        deactivated_on = self.activation.deactivated_on
        if deactivated_on is not None and deactivated_on.value <= effective_start:
            return None

        end_candidates: list[date] = []
        if self.period.valid_to is not None:
            end_candidates.append(self.period.valid_to.value)
        if deactivated_on is not None:
            end_candidates.append(deactivated_on.value - timedelta(days=1))
        effective_end = min(end_candidates) if end_candidates else None
        if effective_end is not None and effective_end < effective_start:
            return None
        return CoveragePeriod(
            valid_from=CoverageValidFrom(effective_start),
            valid_to=(CoverageValidTo(effective_end) if effective_end else None),
        )

    def deactivate(self, effective_on: CoverageDeactivatedOn) -> Self:
        """保険証や公費受給者証の資格喪失日（無効化発効日）を記録する。同一日の再実行は冪等とする。"""
        current = self.activation.deactivated_on
        if current is not None:
            if current == effective_on:
                return self
            raise CoverageDeactivationAlreadyFixedError()
        return replace(
            self,
            activation=replace(self.activation, deactivated_on=effective_on),
        )


_DETAIL_TYPES: dict[CoverageType, tuple[type[object], type[object]]] = {
    CoverageType.INSURANCE: (InsuranceCoverageDetails, _NONE_TYPE),
    CoverageType.PUBLIC_EXPENSE: (_NONE_TYPE, PublicExpenseCoverageDetails),
}
