"""Applicationのupdate_public_expense_designationsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.services.support import load_store_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import PublicExpenseDesignationNumber
from app.domain.store.repositories import StoreRepository
from app.domain.store.value_objects import PublicExpenseDesignations


@dataclass(frozen=True, kw_only=True)
class UpdatePublicExpenseDesignationsCommand:
    """店舗公費・指定医療機関情報更新コマンド。"""

    corporate_id: str
    store_id: str
    public_assistance_number: str | None = None
    support_for_independence_number: str | None = None
    intractable_disease_number: str | None = None
    workers_accident_number: str | None = None


class UpdatePublicExpenseDesignationsUseCase:
    """店舗公費・指定医療機関情報更新ユースケース。"""

    def __init__(
        self, repository: StoreRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdatePublicExpenseDesignationsCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        designations = PublicExpenseDesignations(
            public_assistance_number=(
                PublicExpenseDesignationNumber(command.public_assistance_number)
                if command.public_assistance_number
                else None
            ),
            support_for_independence_number=(
                PublicExpenseDesignationNumber(command.support_for_independence_number)
                if command.support_for_independence_number
                else None
            ),
            intractable_disease_number=(
                PublicExpenseDesignationNumber(command.intractable_disease_number)
                if command.intractable_disease_number
                else None
            ),
            workers_accident_number=(
                PublicExpenseDesignationNumber(command.workers_accident_number)
                if command.workers_accident_number
                else None
            ),
        )
        updated = store.update_public_expense_designations(designations)
        await self._repository.save(updated)
