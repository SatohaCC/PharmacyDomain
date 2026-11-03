"""権限のある店舗の勤務条件を照会する。"""

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import ActorRole, Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError
from app.application.staff.interfaces.store_work_conditions_reader import (
    StoreWorkConditionsReader,
)
from app.application.staff.queries.dtos.store_work_conditions import (
    StoreStaffAffiliationDto,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class GetStoreWorkConditionsQuery:
    corporate_id: str
    staff_id: str
    store_id: str | None = None
    applied_on: date | None = None


class GetStoreWorkConditionsUseCase:
    def __init__(
        self,
        reader: StoreWorkConditionsReader,
        access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._reader = reader
        self._access = access
        self._clock = clock

    async def execute(
        self, query: GetStoreWorkConditionsQuery
    ) -> tuple[StoreStaffAffiliationDto, ...]:
        corporate = CorporateId.parse(query.corporate_id)
        store = StoreId.parse(query.store_id) if query.store_id is not None else None
        actor = self._access.actor
        administrator = bool(
            actor.roles & {ActorRole.VENDOR_SYSTEM_ADMIN, ActorRole.CORPORATE_ADMIN}
        )
        permission = (
            Permission.VIEW_STAFF if administrator else Permission.MANAGE_STORE_USERS
        )
        await self._access.require_active(corporate_id=corporate, permission=permission)
        if not administrator and store is None:
            raise AuthorizationError("管理対象店舗を指定してください。")
        if store is not None:
            AuthorizationService(actor).require_store(
                permission=permission,
                target_corporate_id=corporate,
                target_store_id=store,
            )
        return await self._reader.read(
            corporate_id=corporate,
            staff_id=StaffId.parse(query.staff_id),
            store_id=store,
            applied_on=query.applied_on or business_date(self._clock),
        )
