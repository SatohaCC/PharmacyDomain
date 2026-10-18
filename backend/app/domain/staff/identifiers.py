"""staffの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class StaffId(EntityUUID):
    """スタッフ識別子（UUIDv7）"""

    identifier_name = "スタッフID"
