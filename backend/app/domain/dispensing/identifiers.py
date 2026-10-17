"""調剤セッションの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class DispensingId(EntityUUID):
    """調剤セッション集約の一意識別子（UUIDv7）。"""

    identifier_name = "調剤セッションID"
