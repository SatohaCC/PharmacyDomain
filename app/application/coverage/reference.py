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
        """指定法人内に患者が存在することを確認する。

        Raises:
            CoveragePatientNotFoundError: 患者が存在しない場合、および患者が
                別法人に所属している場合。他テナントのデータは存在を隠すため
                403ではなく404相当のこの例外へ揃える。``AuthorizationError``
                を送出すると他法人の患者IDの存在が呼び出し元へ漏れる。
        """
        ...
