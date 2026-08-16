"""法人単位のスタッフ一覧取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.repository import StaffCatalogRepository
from app.domain.staff.staff import Staff


@dataclass(frozen=True, kw_only=True)
class ListStaffsQuery:
    """スタッフ一覧取得の入力データ（DTO）。"""

    corporate_id: str


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
        )


class ListStaffsUseCase:
    """認可済みの対象法人に所属するスタッフ一覧を取得するユースケース。"""

    def __init__(
        self,
        repository: StaffCatalogRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: ListStaffsQuery) -> list[StaffSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_STAFF,
        )
        staffs = await self._repository.list_by_corporate_id(corporate_id)
        return [StaffSummaryDto.from_entity(staff) for staff in staffs]
