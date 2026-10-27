from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.policy import AuthorizationService
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateName
from app.domain.corporate.repositories import CorporateRepository
from app.domain.corporate.services import CorporateNameUniquenessService
from app.domain.corporate.value_objects import CorporateRepresentativeName
from app.domain.shared.person_name import PersonNamePart


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
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterCorporateCommand) -> CorporateId:
        AuthorizationService(self._corporate_access.actor).require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE,
        )
        name = CorporateName(command.name)
        rep_name = CorporateRepresentativeName(
            last_name=PersonNamePart(command.representative_last_name),
            first_name=PersonNamePart(command.representative_first_name),
        )

        await self._uniqueness_service.ensure_name_is_unique(name=name)

        corporate = Corporate(
            id=CorporateId.generate(), name=name, representative_name=rep_name
        )

        await self._repository.save(corporate)

        return corporate.id
