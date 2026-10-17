"""管理薬剤師任命に必要なスタッフの固定値。"""

from dataclasses import dataclass
from datetime import date

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class ManagerStaffAffiliation(ValueObject):
    """任命期間との包含関係を判断するための所属期間。"""

    store_id: StoreId
    starts_on: date
    ends_on: date | None

    def validate(self) -> None:
        """期間が逆転していないことを保証する。"""
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise DomainValidationError(
                "所属終了日は所属開始日以降で指定してください。"
            )


@dataclass(frozen=True, kw_only=True)
class ManagerStaffSource(ValueObject):
    """スタッフ実装を保持せず、任命の判断材料を固定する。"""

    staff_id: StaffId
    corporate_id: CorporateId
    staff_is_active: bool
    has_pharmacist: bool
    affiliations: tuple[ManagerStaffAffiliation, ...]
