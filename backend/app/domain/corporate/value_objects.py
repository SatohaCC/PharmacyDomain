"""corporateの複合値と参照スナップショット。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import ClassVar

from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateAddressLine,
    CorporateEmailAddress,
    CorporatePageSize,
    CorporatePhoneNumber,
    CorporatePostalCode,
    CorporateSearchText,
    CorporateStatus,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.person_name import PersonName


@dataclass(frozen=True, kw_only=True)
class CorporateAddress(ValueObject):
    """法人の登記上所在地情報。"""

    postal_code: CorporatePostalCode
    address_line: CorporateAddressLine

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "postal_code": "郵便番号",
        "address_line": "住所",
    }


@dataclass(frozen=True, kw_only=True)
class CorporateContactInfo(ValueObject):
    """法人の連絡先情報。"""

    phone_number: CorporatePhoneNumber
    email: CorporateEmailAddress | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "phone_number": "代表電話番号",
        "email": "代表メールアドレス",
    }

    def validate(self) -> None:
        if not self.phone_number.value:
            raise DomainValidationError("代表電話番号は空にできません。")


@dataclass(frozen=True, kw_only=True)
class PolicySetting(ValueObject):
    """ポリシーの単一項目設定。"""

    value: bool = False
    overridable: bool = False


@dataclass(frozen=True, kw_only=True)
class CorporatePolicy(ValueObject):
    """法人ポリシー（集約ルートが所有する設定値）。"""

    require_prescription_audit: PolicySetting = field(default_factory=PolicySetting)
    prohibit_self_verification: PolicySetting = field(default_factory=PolicySetting)


@dataclass(frozen=True, kw_only=True)
class CorporateSearch:
    """検索条件とID順のページ境界。"""

    name: CorporateSearchText | None
    status: CorporateStatus | None
    after_id: CorporateId | None
    limit: CorporatePageSize


class CorporateRepresentativeName(PersonName):
    """代表者の氏名。"""
