"""店舗の管理薬剤師を期間付きで任命する公開契約。"""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.foundation.primitives.primitives import EntityUUID
from app.domain.foundation.value_object import ValueObject
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


class StoreManagerAssignmentId(EntityUUID):
    """管理薬剤師任命の識別子。"""

    identifier_name = "管理薬剤師任命ID"


class ManagerAssignmentStatus(StrEnum):
    """任命の取消状態。"""

    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, kw_only=True)
class ManagerAssignmentPeriod(ValueObject):
    """終了日を含む任命期間。"""

    starts_on: date
    ends_on: date | None = None

    def validate(self) -> None:
        """開始前の終了を拒否する。"""
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise DomainValidationError("任命の終了日は開始日以降にしてください。")

    def contains(self, target_date: date) -> bool:
        """適用日が任命期間に含まれるか。"""
        return self.starts_on <= target_date and (
            self.ends_on is None or target_date <= self.ends_on
        )


@dataclass(frozen=True, eq=False, kw_only=True)
class StoreManagerAssignment(AggregateRoot[StoreManagerAssignmentId]):
    """店舗と人員をIDで結ぶ期間付き任命。"""

    id: StoreManagerAssignmentId
    corporate_id: CorporateId
    store_id: StoreId
    staff_id: StaffId
    period: ManagerAssignmentPeriod
    status: ManagerAssignmentStatus = ManagerAssignmentStatus.CONFIRMED

    def is_effective_on(self, target_date: date) -> bool:
        """取消状態を含めて適用日に有効か判定する。"""
        return (
            self.status == ManagerAssignmentStatus.CONFIRMED
            and self.period.contains(target_date)
        )

    def cancel(self, *, applied_on: date) -> StoreManagerAssignment:
        """開始前の任命を取消し履歴を保持する。"""
        if applied_on >= self.period.starts_on:
            raise DomainError("開始済みの任命は取消ではなく期間を終了してください。")
        return replace(self, status=ManagerAssignmentStatus.CANCELLED)

    def end(self, *, ends_on: date) -> StoreManagerAssignment:
        """任命の期間を終了する。"""
        if self.status != ManagerAssignmentStatus.CONFIRMED:
            raise DomainError("取消済みの任命は終了できません。")
        if self.period.ends_on is not None and ends_on > self.period.ends_on:
            raise DomainError("任命終了では期間を延長できません。")
        return replace(self, period=replace(self.period, ends_on=ends_on))
