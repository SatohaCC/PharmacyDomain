"""corporateのドメインサービス。"""

from __future__ import annotations

from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateName
from app.domain.corporate.repositories import CorporateRepository


class CorporateNameUniquenessService:
    """法人名の重複を防ぐドメインサービス。"""

    def __init__(self, repository: CorporateRepository) -> None:
        self._repository = repository

    async def ensure_name_is_unique(
        self,
        *,
        name: CorporateName,
        excluding_id: CorporateId | None = None,
    ) -> None:

        is_exists = await self._repository.exists_by_name(
            name=name, excluding_id=excluding_id
        )
        if is_exists:
            raise CorporateNameAlreadyExistsError(
                f"法人名 '{name.value}' は既に登録されています。"
            )
