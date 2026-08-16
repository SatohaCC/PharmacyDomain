"""店舗連絡先変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import load_store_or_raise, to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    ContactInfo,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreId,
    StorePhoneNumber,
)
from app.domain.store.repository import StoreRepository


@dataclass(frozen=True, kw_only=True)
class ChangeStoreContactInfoCommand:
    """店舗連絡先変更に必要な入力データ（DTO）。"""

    corporate_id: str
    store_id: str
    phone_number: str
    fax_number: str | None = None
    email: str | None = None


class ChangeStoreContactInfoUseCase:
    """店舗連絡先変更ユースケース。"""

    def __init__(
        self,
        repository: StoreRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ChangeStoreContactInfoCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )
        store_id = StoreId.parse(command.store_id)
        raw_fax_number = to_optional_text(command.fax_number)
        raw_email = to_optional_text(command.email)
        new_contact_info = ContactInfo.create(
            phone_number=StorePhoneNumber(command.phone_number),
            fax_number=(StoreFaxNumber(raw_fax_number) if raw_fax_number else None),
            email=StoreEmailAddress(raw_email) if raw_email else None,
        )

        store = await load_store_or_raise(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store.contact_info == new_contact_info:
            return

        store = store.change_contact_info(new_contact_info)
        await self._repository.save(store)
