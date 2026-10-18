"""corporateの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class CorporateId(EntityUUID):
    """法人の一意識別子（UUIDv7）"""

    identifier_name = "法人ID"
