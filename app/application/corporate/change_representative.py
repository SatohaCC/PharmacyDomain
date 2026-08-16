from dataclasses import dataclass

from app.application.access_control import Permission
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.corporate.primitives import (
    CorporateId,
    CorporateRepresentativeName,
)
from app.domain.corporate.repository import CorporateRepository


@dataclass(frozen=True, kw_only=True)
class ChangeRepresentativeCommand:
    """代表者変更に必要な入力データ（DTO）"""

    corporate_id: str
    new_last_name: str
    new_first_name: str


class ChangeRepresentativeUseCase:
    """代表者名変更ユースケース"""

    def __init__(
        self,
        repository: CorporateRepository,
        corporate_access: CorporateAccessService,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeRepresentativeCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        new_representative_name = CorporateRepresentativeName.create(
            last_name=command.new_last_name,
            first_name=command.new_first_name,
        )

        corporate = await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_CORPORATE,
        )

        if corporate.representative_name == new_representative_name:
            return

        corporate = corporate.change_representative(new_representative_name)

        await self._repository.save(corporate)
