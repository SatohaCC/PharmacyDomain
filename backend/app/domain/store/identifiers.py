"""storeの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class StoreManagerAssignmentId(EntityUUID):
    """管理薬剤師任命の識別子。"""

    identifier_name = "管理薬剤師任命ID"


class StoreId(EntityUUID):
    """店舗識別子（UUIDv7）"""

    identifier_name = "店舗ID"
