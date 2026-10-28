"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.patient.interfaces.get_patient_heading_query_reader import (
    GetPatientHeadingQueryReader,
)
from app.application.patient.queries.dtos.get_patient_heading import PatientHeadingDto
from app.application.patient.queries.models import GetPatientHeadingQuery
from app.application.patient.queries.services.get_patient_heading import _to_dto
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import PatientRepository
from app.infrastructure.readers.helpers.patient_support import load_patient_or_raise


class GetPatientHeadingProjection(GetPatientHeadingQueryReader):
    """患者頭書きを参照するユースケース契約。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def read(self, query: GetPatientHeadingQuery) -> PatientHeadingDto:
        """認可と法人境界を確かめて頭書きを取得する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=PatientId.parse(query.patient_id),
        )
        return _to_dto(str(patient.id.value), patient.heading_history)
