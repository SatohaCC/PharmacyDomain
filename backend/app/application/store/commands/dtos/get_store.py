"""Applicationのget_storeを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.store.commands.dtos.business_hours import BusinessHoursDto
from app.domain.store.entities import Store


@dataclass(frozen=True, kw_only=True)
class StoreStatusChangeDto:
    """状態履歴の公開値。"""

    before: str
    after: str
    reason: str
    person_id: str
    account_id: str
    recorded_at: datetime


@dataclass(frozen=True, kw_only=True)
class StoreDto:
    """店舗詳細の出力データ（DTO）"""

    id: str
    corporate_id: str
    name: str
    name_kana: str
    name_romaji: str | None
    postal_code: str
    address: str
    phone_number: str
    fax_number: str | None
    email: str | None
    code: str | None
    insurance_pharmacy_number: str | None
    status: str
    status_history: tuple[StoreStatusChangeDto, ...]
    business_hours: BusinessHoursDto | None

    @classmethod
    def from_entity(cls, store: Store) -> StoreDto:
        """Store エンティティから DTO を生成するファクトリメソッド"""
        return cls(
            business_hours=BusinessHoursDto.from_value(store.business_hours)
            if store.business_hours is not None
            else None,
            status=store.status.value,
            status_history=tuple(
                StoreStatusChangeDto(
                    before=item.before.value,
                    after=item.after.value,
                    reason=item.reason.value,
                    person_id=str(item.person_id.value),
                    account_id=str(item.account_id.value),
                    recorded_at=item.recorded_at,
                )
                for item in store.status_history
            ),
            id=str(store.id.value),
            corporate_id=str(store.corporate_id.value),
            name=store.names.name.value,
            name_kana=store.names.kana.value,
            name_romaji=store.names.romaji.value if store.names.romaji else None,
            postal_code=store.address.postal_code.value,
            address=store.address.address.value,
            phone_number=store.contact_info.phone_number.value,
            fax_number=store.contact_info.fax_number.value
            if store.contact_info.fax_number
            else None,
            email=store.contact_info.email.value if store.contact_info.email else None,
            code=store.code.value if store.code else None,
            insurance_pharmacy_number=store.insurance_pharmacy_number.value
            if store.insurance_pharmacy_number
            else None,
        )
