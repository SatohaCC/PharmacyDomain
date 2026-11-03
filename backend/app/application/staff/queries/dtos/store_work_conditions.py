"""店舗別勤務条件の参照値。"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, kw_only=True)
class StoreWorkConditionDto:
    """適用・訂正順を保った勤務条件の記録。"""

    effective_from: date
    weekly_hours: str | None
    duty: str
    recorded_at: datetime
    recorded_by: str


@dataclass(frozen=True, kw_only=True)
class StoreStaffAffiliationDto:
    """所属期間と対象日時点の条件、訂正を含む履歴。"""

    store_id: str
    starts_on: date
    ends_on: date | None
    is_primary: bool
    is_managing_pharmacist: bool
    current: StoreWorkConditionDto | None
    history: tuple[StoreWorkConditionDto, ...]
