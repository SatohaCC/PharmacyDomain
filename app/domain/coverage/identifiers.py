"""保険資格と適用履歴の公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class PatientCoverageId(EntityUUID):
    """患者資格の一意識別子（UUIDv7）。"""

    identifier_name = "患者資格ID"


class CoverageSelectionRecordId(EntityUUID):
    """適用資格選択履歴の一意識別子。"""

    identifier_name = "適用資格選択履歴ID"
