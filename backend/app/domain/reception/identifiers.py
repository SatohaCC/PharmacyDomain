"""receptionの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class ReceptionId(EntityUUID):
    """受付の安定識別子。"""

    identifier_name = "受付ID"
