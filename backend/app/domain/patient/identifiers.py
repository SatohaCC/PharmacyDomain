"""patientの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class PatientId(EntityUUID):
    """患者の一意識別子（UUIDv7）。"""

    identifier_name = "患者ID"


class PatientExternalIdentifierId(EntityUUID):
    """患者外部識別子の一意識別子（UUIDv7）。"""

    identifier_name = "患者外部識別子ID"
