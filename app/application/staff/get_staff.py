"""スタッフ詳細取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.common.clock import Clock
from app.application.staff.support import load_staff_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.primitives import StaffId
from app.domain.staff.repository import StaffRepository
from app.domain.staff.staff import Staff


@dataclass(frozen=True, kw_only=True)
class GetStaffQuery:
    """スタッフ詳細取得の入力データ（DTO）。"""

    corporate_id: str
    staff_id: str
    target_date: date | None = None


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
        )


class GetStaffUseCase:
    """スタッフ詳細取得ユースケース。"""

    def __init__(
        self,
        repository: StaffRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, query: GetStaffQuery) -> StaffDto:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_STAFF,
        )
        staff_id = StaffId.parse(query.staff_id)

        staff = await load_staff_or_raise(
            self._repository,
            corporate_id=corporate_id,
            staff_id=staff_id,
        )

        target_date = query.target_date or self._clock.now().date()
        return StaffDto.from_entity(staff, target_date=target_date)
