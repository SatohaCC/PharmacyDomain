from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.corporate.primitives import CorporateId, CorporateName
from app.domain.corporate.repository import CorporateRepository


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
