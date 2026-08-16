from dataclasses import dataclass

from app.application.access_control import Permission
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.corporate.primitives import CorporateId, CorporateName
from app.domain.corporate.repository import CorporateRepository
from app.domain.corporate.services import CorporateNameUniquenessService


@dataclass(frozen=True, kw_only=True)
class ChangeCorporateNameCommand:
    """法人名変更に必要な入力データ（DTO）"""

    corporate_id: str
    new_name: str


class ChangeCorporateNameUseCase:
    """法人名変更ユースケース"""

    def __init__(
        self,
        repository: CorporateRepository,
        uniqueness_service: CorporateNameUniquenessService,
        corporate_access: CorporateAccessService,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeCorporateNameCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        new_name = CorporateName(command.new_name)

        corporate = await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_CORPORATE,
        )

        if corporate.name == new_name:
            return

        await self._uniqueness_service.ensure_name_is_unique(
            name=new_name,
            excluding_id=corporate_id,
        )

        corporate = corporate.change_name(new_name)

        await self._repository.save(corporate)
