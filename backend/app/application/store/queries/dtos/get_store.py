"""Applicationのget_storeを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.application.store.queries.dtos.business_hours import BusinessHoursDto
from app.domain.store.entities import Store


@dataclass(frozen=True, kw_only=True)
class PharmacyLicenseDto:
    """薬局開設許可の出力データ。"""

    number: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class NarcoticsRetailerLicenseDto:
    """麻薬小売業者免許の出力データ。"""

    number: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class StoreLicensesDto:
    """店舗許認可の出力データ。"""

    pharmacy_license: PharmacyLicenseDto
    narcotics_retailer_license: NarcoticsRetailerLicenseDto | None = None


@dataclass(frozen=True, kw_only=True)
class StorePolicyDto:
    """店舗ポリシーの出力データ。"""

    require_prescription_audit: bool | None = None
    prohibit_self_verification: bool | None = None


@dataclass(frozen=True, kw_only=True)
class StoreStatusChangeDto:
    """状態履歴の公開値。"""

    before: str
    after: str
    reason: str
    recorded_at: datetime
    person_id: str | None = None
    account_id: str | None = None
    operator_id: str | None = None


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
    licenses: StoreLicensesDto | None = None
    policy: StorePolicyDto | None = None

    @classmethod
    def from_entity(cls, store: Store) -> StoreDto:
        """Store エンティティから DTO を生成するファクトリメソッド"""
        return cls(
            policy=StorePolicyDto(
                require_prescription_audit=store.policy.require_prescription_audit,
                prohibit_self_verification=store.policy.prohibit_self_verification,
            ),
            licenses=(
                StoreLicensesDto(
                    pharmacy_license=PharmacyLicenseDto(
                        number=store.licenses.pharmacy_license.number.value,
                        valid_from=store.licenses.pharmacy_license.valid_from,
                        valid_to=store.licenses.pharmacy_license.valid_to,
                    ),
                    narcotics_retailer_license=(
                        NarcoticsRetailerLicenseDto(
                            number=store.licenses.narcotics_retailer_license.number.value,
                            valid_from=store.licenses.narcotics_retailer_license.valid_from,
                            valid_to=store.licenses.narcotics_retailer_license.valid_to,
                        )
                        if store.licenses.narcotics_retailer_license is not None
                        else None
                    ),
                )
                if store.licenses is not None
                else None
            ),
            business_hours=BusinessHoursDto.from_value(store.business_hours)
            if store.business_hours is not None
            else None,
            status=store.status.value,
            status_history=tuple(
                StoreStatusChangeDto(
                    before=item.before.value,
                    after=item.after.value,
                    reason=item.reason.value,
                    person_id=str(item.person_id.value) if item.person_id else None,
                    account_id=str(item.account_id.value) if item.account_id else None,
                    operator_id=str(item.operator_id.value)
                    if item.operator_id
                    else None,
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
