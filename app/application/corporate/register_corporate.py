from dataclasses import dataclass

from app.application.access_control import Permission
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.corporate import (
    Corporate,
    CorporateId,
    CorporateName,
    CorporateNameUniquenessService,
    CorporateRepository,
    CorporateRepresentativeName,
)


@dataclass(frozen=True, kw_only=True)
class RegisterCorporateCommand:
    """法人登録に必要なパラメータをまとめた Command (DTO)"""

    name: str
    representative_last_name: str
    representative_first_name: str


class RegisterCorporateUseCase:
    """法人を新規登録するアプリケーションサービス"""

    def __init__(
        self,
        repository: CorporateRepository,
        uniqueness_service: CorporateNameUniquenessService,
        corporate_access: CorporateAccessService,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterCorporateCommand) -> CorporateId:
        self._corporate_access.require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE,
        )
        name = CorporateName(command.name)
        rep_name = CorporateRepresentativeName.create(
            last_name=command.representative_last_name,
            first_name=command.representative_first_name,
        )

        await self._uniqueness_service.ensure_name_is_unique(name=name)

        corporate = Corporate.create(name=name, representative_name=rep_name)

        await self._repository.save(corporate)

        return corporate.id
