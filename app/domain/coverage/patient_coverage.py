"""患者の健康保険証・公費受給者証などの保険資格（台帳情報）を管理するモジュール。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import (
    CoverageDeactivationAlreadyFixedError,
    CoverageDetailsMismatchError,
    InsuranceCoveragePriorityError,
)
from app.domain.coverage.primitives import (
    CoverageActivation,
    CoverageDeactivatedOn,
    CoveragePeriod,
    CoveragePriority,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    InsuranceCoverageDetails,
    PatientCoverageId,
    PublicExpenseCoverageDetails,
)
from app.domain.foundation.entity import AggregateRoot
from app.domain.patient.primitives import PatientId

_NONE_TYPE = type(None)
_DETAIL_TYPES: dict[CoverageType, tuple[type[object], type[object]]] = {
    CoverageType.INSURANCE: (InsuranceCoverageDetails, _NONE_TYPE),
    CoverageType.PUBLIC_EXPENSE: (_NONE_TYPE, PublicExpenseCoverageDetails),
}

if set(_DETAIL_TYPES) != set(CoverageType):
    raise RuntimeError("CoverageType の制度別詳細型分類に漏れがあります。")


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

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_type: CoverageType,
        period: CoveragePeriod,
        activation: CoverageActivation,
        priority: CoveragePriority,
        insurance_details: InsuranceCoverageDetails | None = None,
        public_expense_details: PublicExpenseCoverageDetails | None = None,
    ) -> Self:
        """患者の保険資格（保険証または公費受給者証情報）を新規登録する。"""
        return cls(
            id=PatientCoverageId.generate(),
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_type=coverage_type,
            period=period,
            activation=activation,
            priority=priority,
            insurance_details=insurance_details,
            public_expense_details=public_expense_details,
        )

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
