"""prescriptionの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class PrescriptionId(EntityUUID):
    """処方箋集約の一意識別子（UUIDv7）。"""

    identifier_name = "処方箋ID"
