"""Coverageの参照境界を患者Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from app.application.coverage.exceptions import CoveragePatientNotFoundError
from app.application.coverage.reference import PatientReferenceBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


class CoveragePatientReferenceAdapter(PatientReferenceBoundary):
    """患者の存在と法人境界だけを確認し、患者集約は渡さない。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """未存在・別法人の患者を、存在を隠す404相当へ畳む。

        ``PatientRepository.get()`` が他法人の患者へ ``None`` を返す契約なので、
        法人境界の判定はRepositoryに委ねられる。
        """
        patient = await self._repository.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            raise CoveragePatientNotFoundError()
