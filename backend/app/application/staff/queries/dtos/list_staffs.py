"""Applicationのlist_staffsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.staff.entities import Staff


@dataclass(frozen=True, kw_only=True)
class StaffSummaryDto:
    """スタッフ一覧の出力データ（DTO）。"""

    id: str
    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    code: str | None
    job_title: str | None
    is_active: bool
    is_pharmacist: bool
    employment_type: str = "regular"
    status: str = "active"
    leave_reason: str | None = None
    weekly_contract_hours: float | None = None
    effective_full_time_equivalent: float = 0.0

    @classmethod
    def from_entity(cls, staff: Staff) -> StaffSummaryDto:
        return cls(
            id=str(staff.id.value),
            corporate_id=str(staff.corporate_id.value),
            last_name=staff.names.kanji.last_name.value,
            first_name=staff.names.kanji.first_name.value,
            last_name_kana=staff.names.kana.last_name.value,
            first_name_kana=staff.names.kana.first_name.value,
            code=staff.code.value if staff.code else None,
            job_title=staff.job_title.value if staff.job_title else None,
            is_active=staff.is_active,
            is_pharmacist=staff.is_pharmacist,
            employment_type=staff.employment_type.value,
            status=staff.status.value,
            leave_reason=staff.leave_reason.value if staff.leave_reason else None,
            weekly_contract_hours=(
                float(staff.weekly_contract_hours.value)
                if staff.weekly_contract_hours
                else None
            ),
            effective_full_time_equivalent=float(
                staff.effective_full_time_equivalent()
            ),
        )
