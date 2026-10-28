"""Applicationのget_corporateを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.corporate.interfaces.corporate_access import (
    ExistingCorporateAccessBoundary,
)
from app.application.corporate.queries.dtos.get_corporate import CorporateResponseDto
from app.domain.corporate.identifiers import CorporateId


class GetCorporateUseCase:
    """法人取得ユースケース（アプリケーションサービス）"""

    def __init__(self, corporate_access: ExistingCorporateAccessBoundary) -> None:
        self._corporate_access = corporate_access

    async def execute(self, corporate_id_str: str) -> CorporateResponseDto:
        corporate_id = CorporateId.parse(corporate_id_str)
        corporate = await self._corporate_access.require_existing(
            corporate_id=corporate_id, permission=Permission.VIEW_CORPORATE
        )
        return CorporateResponseDto.from_entity(corporate)
