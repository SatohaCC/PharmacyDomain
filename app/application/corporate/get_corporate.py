from dataclasses import dataclass
from typing import Self

from app.application.access_control import Permission
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId


@dataclass(frozen=True, kw_only=True)
class CorporateResponseDto:
    """取得結果として画面やAPIに返すデータ構造（DTO）"""

    id: str
    name: str
    representative_name: str
    is_active: bool

    @classmethod
    def from_entity(cls, corporate: Corporate) -> Self:
        """Corporate エンティティから DTO を復元するファクトリメソッド"""
        return cls(
            id=str(corporate.id.value),
            name=corporate.name.value,
            representative_name=corporate.representative_name.full_name,
            is_active=corporate.is_active,
        )


class GetCorporateUseCase:
    """法人取得ユースケース（アプリケーションサービス）"""

    def __init__(self, corporate_access: CorporateAccessService) -> None:
        self._corporate_access = corporate_access

    async def execute(self, corporate_id_str: str) -> CorporateResponseDto:
        corporate_id = CorporateId.parse(corporate_id_str)

        corporate = await self._corporate_access.require_existing(
            corporate_id=corporate_id,
            permission=Permission.VIEW_CORPORATE,
        )

        return CorporateResponseDto.from_entity(corporate)
