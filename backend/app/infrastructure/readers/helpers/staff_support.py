"""Applicationのstaff_supportを定義する。"""

from __future__ import annotations

from app.application.staff.errors import StaffNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository


async def load_staff_or_raise(
    repository: StaffRepository, *, corporate_id: CorporateId, staff_id: StaffId
) -> Staff:
    """指定された法人に所属するスタッフを取得し、存在しないまたは別法人の場合は例外を送出する。"""
    staff = await repository.get(corporate_id=corporate_id, staff_id=staff_id)
    if staff is None:
        raise StaffNotFoundError(
            f"指定されたスタッフ（ID: {staff_id.value}）が見つかりません。"
        )
    return staff
