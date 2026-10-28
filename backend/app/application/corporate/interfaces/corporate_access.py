"""法人参照に必要な認可済み読取の契約。"""

from typing import Protocol

from app.application.access_control.boundary_models import Permission
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId


class ExistingCorporateAccessBoundary(Protocol):
    async def require_existing(
        self, *, corporate_id: CorporateId, permission: Permission
    ) -> Corporate:
        """認可と存在確認を行い、未存在・他法人は404相当として拒否する。"""
        ...
