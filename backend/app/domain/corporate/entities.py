"""corporateのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateName,
    CorporateNumber,
    CorporateStatus,
    CorporateType,
    InvoiceRegistrationNumber,
)
from app.domain.corporate.value_objects import (
    CorporateAddress,
    CorporateContactInfo,
    CorporatePolicy,
    CorporateRepresentativeName,
)
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError


@dataclass(frozen=True, eq=False, kw_only=True)
class Corporate(AggregateRoot[CorporateId]):
    """法人エンティティ（集約ルート）。複数の薬局店舗を束ねるマルチテナントの境界"""

    id: CorporateId
    name: CorporateName
    representative_name: CorporateRepresentativeName
    corporate_type: CorporateType = CorporateType.STOCK_COMPANY
    corporate_number: CorporateNumber | None = None
    invoice_number: InvoiceRegistrationNumber | None = None
    address: CorporateAddress | None = None
    contact_info: CorporateContactInfo | None = None
    status: CorporateStatus = CorporateStatus.ACTIVE
    policy: CorporatePolicy = field(default_factory=CorporatePolicy)

    def validate(self) -> None:
        """法人番号とインボイス番号の整合性を検証する。"""
        if (
            self.corporate_number is not None
            and self.invoice_number is not None
            and not self.invoice_number.matches_corporate_number(self.corporate_number)
        ):
            raise DomainValidationError(
                "適格請求書発行事業者登録番号は法人番号と一致している必要があります。"
            )

    def change_name(self, new_name: CorporateName) -> Self:
        """法人名を変更する"""
        return replace(self, name=new_name)

    def change_representative(
        self, new_representative_name: CorporateRepresentativeName
    ) -> Self:
        """代表者名を変更する"""
        return replace(self, representative_name=new_representative_name)

    def change_corporate_type(self, new_type: CorporateType) -> Self:
        """法人格を変更する"""
        return replace(self, corporate_type=new_type)

    def update_corporate_number(self, new_number: CorporateNumber | None) -> Self:
        """法人番号を更新または解除する"""
        return replace(self, corporate_number=new_number)

    def update_invoice_number(
        self, new_invoice_number: InvoiceRegistrationNumber | None
    ) -> Self:
        """適格請求書発行事業者登録番号を更新または解除する"""
        return replace(self, invoice_number=new_invoice_number)

    def change_address(self, new_address: CorporateAddress | None) -> Self:
        """登記上所在地を変更する"""
        return replace(self, address=new_address)

    def change_contact_info(
        self, new_contact_info: CorporateContactInfo | None
    ) -> Self:
        """代表連絡先を変更する"""
        return replace(self, contact_info=new_contact_info)

    def change_policy(self, new_policy: CorporatePolicy) -> Self:
        """法人ポリシーを変更する"""
        return replace(self, policy=new_policy)

    @property
    def is_active(self) -> bool:
        """通常の店舗・スタッフ操作を受け付けられる状態か判定する。"""
        return self.status is CorporateStatus.ACTIVE

    def activate(self) -> Self:
        """法人を利用可能な状態へ変更する。"""
        return replace(self, status=CorporateStatus.ACTIVE)

    def deactivate(self) -> Self:
        """法人を利用停止状態へ変更する。"""
        return replace(self, status=CorporateStatus.INACTIVE)
