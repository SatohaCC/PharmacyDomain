"""identityの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class CorporateMembershipId(EntityUUID):
    """法人アクセス権の識別子。"""

    identifier_name = "法人アクセス権ID"


class VendorOperatorId(EntityUUID):
    """運営者（システム管理者）の識別子。"""

    identifier_name = "運営者ID"
