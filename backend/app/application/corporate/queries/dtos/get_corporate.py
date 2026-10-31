"""Applicationのget_corporateを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.domain.corporate.entities import Corporate


@dataclass(frozen=True, kw_only=True)
class PolicySettingDto:
    """ポリシー単一項目の出力データ。"""

    value: bool
    overridable: bool


@dataclass(frozen=True, kw_only=True)
class CorporatePolicyDto:
    """法人ポリシーの出力データ。"""

    require_prescription_audit: PolicySettingDto
    prohibit_self_verification: PolicySettingDto


@dataclass(frozen=True, kw_only=True)
class CorporateResponseDto:
    """取得結果として画面やAPIに返すデータ構造（DTO）"""

    id: str
    name: str
    representative_name: str
    is_active: bool
    policy: CorporatePolicyDto
    corporate_type: str = "stock_company"
    corporate_number: str | None = None
    invoice_number: str | None = None
    postal_code: str | None = None
    address_line: str | None = None
    phone_number: str | None = None
    email: str | None = None

    @classmethod
    def from_entity(cls, corporate: Corporate) -> Self:
        """Corporate エンティティから DTO を復元するファクトリメソッド"""
        return cls(
            id=str(corporate.id.value),
            name=corporate.name.value,
            representative_name=corporate.representative_name.full_name,
            is_active=corporate.is_active,
            policy=CorporatePolicyDto(
                require_prescription_audit=PolicySettingDto(
                    value=corporate.policy.require_prescription_audit.value,
                    overridable=corporate.policy.require_prescription_audit.overridable,
                ),
                prohibit_self_verification=PolicySettingDto(
                    value=corporate.policy.prohibit_self_verification.value,
                    overridable=corporate.policy.prohibit_self_verification.overridable,
                ),
            ),
            corporate_type=corporate.corporate_type.value,
            corporate_number=(
                corporate.corporate_number.value if corporate.corporate_number else None
            ),
            invoice_number=(
                corporate.invoice_number.value if corporate.invoice_number else None
            ),
            postal_code=(
                corporate.address.postal_code.value if corporate.address else None
            ),
            address_line=(
                corporate.address.address_line.value if corporate.address else None
            ),
            phone_number=(
                corporate.contact_info.phone_number.value
                if corporate.contact_info
                else None
            ),
            email=(
                corporate.contact_info.email.value
                if corporate.contact_info and corporate.contact_info.email
                else None
            ),
        )
