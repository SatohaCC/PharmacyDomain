"""初期管理者へのスタッフ紐付け境界。"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.person_name import PersonNames
from app.domain.staff.identifiers import StaffId


class StaffCreationBoundary(Protocol):
    """初期管理者に対するスタッフ集約の生成と保存を提供する。"""

    async def create_staff(
        self,
        *,
        corporate_id: CorporateId,
        names: PersonNames,
        code: str | None,
        job_title: str | None,
        phone_number: str | None,
        email: str | None,
        initial_home_store_id: str | None,
        initial_start_date: date | None,
        pharmacist_license_number: str | None,
        insurance_pharmacist_registration_number: str | None,
        insurance_pharmacist_registration_date: date | None,
        registered_seller_number: str | None,
        dietitian_registration_number: str | None,
        is_registered_dietitian: bool,
    ) -> StaffId:
        """スタッフ集約を保存し、採番されたIDを返す。"""
        ...
