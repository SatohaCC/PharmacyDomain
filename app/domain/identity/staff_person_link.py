"""法人内のスタッフと本人の対応を永続的に固定する。"""

from dataclasses import dataclass

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.identity.primitives import AccountPersonId
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, eq=False, kw_only=True)
class StaffPersonLink(AggregateRoot[StaffId]):
    """同じStaffを別人へ付け替えないための独立した対応記録。"""

    id: StaffId
    corporate_id: CorporateId
    person_id: AccountPersonId
