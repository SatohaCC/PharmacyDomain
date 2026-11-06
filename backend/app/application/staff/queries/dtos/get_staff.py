"""Applicationのget_staffを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.staff.entities import Staff


@dataclass(frozen=True, kw_only=True)
class StaffDto:
    """スタッフ詳細の出力データ（DTO）。"""

    id: str
    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    job_title: str | None
    code: str | None
    phone_number: str | None
    email: str | None
    is_active: bool
    is_pharmacist: bool
    is_dietitian: bool
    is_registered_seller: bool
    current_home_store_id: str | None
    employment_type: str = "regular"
    status: str = "active"
    leave_reason: str | None = None
    weekly_contract_hours: float | None = None
    effective_weekly_hours: float = 0.0
    effective_full_time_equivalent: float = 0.0

    @classmethod
    def from_entity(cls, staff: Staff, *, target_date: date) -> StaffDto:
        """指定日時点の導出値を含むDTOへ変換する。

        適用日は必ず呼び出し側が渡す。既定値として ``date.today()`` を使うと
        「いつ時点の主所属か」が暗黙になり、注入した ``Clock`` を迂回してしまう。
        """
        home_store_id = staff.current_home_store_id(target_date)
        return cls(
            id=str(staff.id.value),
            corporate_id=str(staff.corporate_id.value),
            last_name=staff.names.kanji.last_name.value,
            first_name=staff.names.kanji.first_name.value,
            last_name_kana=staff.names.kana.last_name.value,
            first_name_kana=staff.names.kana.first_name.value,
            job_title=staff.job_title.value if staff.job_title else None,
            code=staff.code.value if staff.code else None,
            phone_number=staff.phone_number.value if staff.phone_number else None,
            email=staff.email.value if staff.email else None,
            is_active=staff.is_active,
            is_pharmacist=staff.is_pharmacist,
            is_dietitian=staff.is_dietitian,
            is_registered_seller=staff.is_registered_seller,
            current_home_store_id=str(home_store_id.value) if home_store_id else None,
            employment_type=staff.employment_type.value,
            status=staff.status.value,
            leave_reason=staff.leave_reason.value if staff.leave_reason else None,
            weekly_contract_hours=(
                float(staff.weekly_contract_hours.value)
                if staff.weekly_contract_hours
                else None
            ),
            effective_weekly_hours=float(staff.effective_weekly_hours),
            effective_full_time_equivalent=float(
                staff.effective_full_time_equivalent()
            ),
        )
