"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.patient.interfaces.get_patient_query_reader import (
    GetPatientQueryReader,
)
from app.application.patient.queries.dtos.get_patient import PatientDto
from app.application.patient.queries.models import GetPatientQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import PatientRepository
from app.infrastructure.readers.helpers.patient_support import load_patient_or_raise


class GetPatientProjection(GetPatientQueryReader):
    """患者詳細を取得するアプリケーションサービス。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def read(self, query: GetPatientQuery) -> PatientDto:
        """法人境界を確認して患者情報DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        patient_id = PatientId.parse(query.patient_id)
        patient = await load_patient_or_raise(
            self._repository, corporate_id=corporate_id, patient_id=patient_id
        )
        return PatientDto.from_entity(patient)
