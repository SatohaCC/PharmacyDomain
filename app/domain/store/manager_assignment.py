"""店舗の管理薬剤師を期間付きで任命する公開契約。"""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.foundation.primitives.primitives import EntityUUID
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


class StoreManagerAssignmentId(EntityUUID):
    """管理薬剤師任命の識別子。"""

    identifier_name = "管理薬剤師任命ID"


class ManagerAssignmentStateConflictError(DomainError):
    """任命の現在状態と要求された操作が競合する。

    基底の ``DomainError`` を直接送出すると、``errors.py`` の対応表で個別に
    扱えず、クライアントは開始済み任命の取消も期間の延長も同じ符号で受け取る。
    """

    default_code = "MANAGER_ASSIGNMENT_STATE_CONFLICT"


class ManagerAbsenceConflictError(DomainError):
    """管理薬剤師が在任していない店舗で、新しい業務を始めようとした。

    店舗状態の競合（``StoreStateConflictError``）とは別の符号にする。休止中の
    店舗と管理薬剤師のいない店舗では、利用者が次に取る手段が違う（前者は店舗を
    再開する、後者は任命する）ので、同じ符号へ畳むと分岐を書けない。
    """

    default_code = "MANAGER_ABSENCE_CONFLICT"


class ManagerPersonUnresolvedError(DomainError):
    """任命しようとしたスタッフに、本人が固定されていない。

    専任義務は自然人にかかるので、本人の分からないスタッフを任命すると、その
    1件だけが兼務の検査をすり抜ける。「分からないなら通す」に倒さない。
    """

    default_code = "MANAGER_PERSON_UNRESOLVED"


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
    #: そのスタッフに対応する自然人。専任義務（薬機法第7条第3項）は法人内の
    #: スタッフではなく人にかかるため、法人をまたいで競合を判定できる鍵が要る。
    #: スタッフと本人の対応は付け替えを封じてあるので、ここへ写しても後から
    #: 食い違わない。写しであることは複合外部キーがDB側でも保証する。
    person_id: AccountPersonId
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
            raise ManagerAssignmentStateConflictError(
                "開始済みの任命は取消ではなく期間を終了してください。"
            )
        return replace(self, status=ManagerAssignmentStatus.CANCELLED)

    def end(self, *, ends_on: date) -> StoreManagerAssignment:
        """任命の期間を終了する。"""
        if self.status != ManagerAssignmentStatus.CONFIRMED:
            raise ManagerAssignmentStateConflictError(
                "取消済みの任命は終了できません。"
            )
        if self.period.ends_on is not None and ends_on > self.period.ends_on:
            raise ManagerAssignmentStateConflictError(
                "任命終了では期間を延長できません。"
            )
        return replace(self, period=replace(self.period, ends_on=ends_on))
