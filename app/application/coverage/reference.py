"""Coverageから患者をIDだけで参照する境界。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId


class PatientReferenceBoundary(Protocol):
    """患者エンティティを渡さず、患者IDの存在だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人内に患者が存在することを確認する。"""
        ...
