"""corporateの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporatePageSize,
    CorporateSearchText,
    CorporateStatus,
)
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.person_name import PersonName


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
