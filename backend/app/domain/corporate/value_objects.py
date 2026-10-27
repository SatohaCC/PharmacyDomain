"""corporateの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporatePageSize,
    CorporateSearchText,
    CorporateStatus,
)
from app.domain.shared.person_name import PersonName


@dataclass(frozen=True, kw_only=True)
class CorporateSearch:
    """検索条件とID順のページ境界。"""

    name: CorporateSearchText | None
    status: CorporateStatus | None
    after_id: CorporateId | None
    limit: CorporatePageSize


class CorporateRepresentativeName(PersonName):
    """代表者の氏名。"""
