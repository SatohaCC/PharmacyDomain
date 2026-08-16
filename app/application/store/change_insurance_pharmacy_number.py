"""保険薬局指定番号変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise, to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    StoreId,
)
from app.domain.store.repository import StoreRepository
from app.domain.store.services import InsurancePharmacyNumberUniquenessService


@dataclass(frozen=True, kw_only=True)
class ChangeInsurancePharmacyNumberCommand:
    """保険薬局指定番号変更に必要な入力データ（DTO）。"""

    corporate_id: str
    store_id: str
    #: ``None``・空文字・空白のみはいずれも指定番号の解除を意味する。
    new_number: str | None


class ChangeInsurancePharmacyNumberUseCase:
    """保険薬局指定番号変更ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        uniqueness_service: InsurancePharmacyNumberUniquenessService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._uniqueness_service = uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeInsurancePharmacyNumberCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )
        store_id = StoreId.parse(command.store_id)
        raw_number = to_optional_text(command.new_number)
        new_number = InsurancePharmacyNumber(raw_number) if raw_number else None

        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store.insurance_pharmacy_number == new_number:
            return

        if new_number is not None:
            await self._uniqueness_service.ensure_number_is_unique(
                number=new_number,
                excluding_id=store_id,
            )

        store = store.change_insurance_pharmacy_number(new_number)
        await self._repository.save(store)
