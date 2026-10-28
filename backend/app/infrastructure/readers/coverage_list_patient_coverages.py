"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.coverage.interfaces.list_patient_coverages_query_reader import (
    ListPatientCoveragesQueryReader,
)
from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto,
)
from app.application.coverage.queries.models import ListPatientCoveragesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.repositories import PatientCoverageRepository
from app.domain.patient.identifiers import PatientId


class ListPatientCoveragesProjection(ListPatientCoveragesQueryReader):
    """患者に紐付く資格一覧を取得する。"""

    def __init__(self, repository: PatientCoverageRepository) -> None:
        self._repository = repository

    async def read(self, query: ListPatientCoveragesQuery) -> list[PatientCoverageDto]:
        """法人・患者の存在を確認して資格一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        patient_id = PatientId.parse(query.patient_id)
        coverages = await self._repository.list_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return [PatientCoverageDto.from_entity(item) for item in coverages]
