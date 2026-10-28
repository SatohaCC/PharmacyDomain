"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.coverage.interfaces.get_patient_coverage_query_reader import (
    GetPatientCoverageQueryReader,
)
from app.application.coverage.queries.dtos.get_patient_coverage import (
    PatientCoverageDto,
)
from app.application.coverage.queries.models import GetPatientCoverageQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.identifiers import PatientCoverageId
from app.domain.coverage.repositories import PatientCoverageRepository
from app.infrastructure.readers.helpers.coverage_support import load_coverage_or_raise


class GetPatientCoverageProjection(GetPatientCoverageQueryReader):
    """患者資格を取得してDTOを返すアプリケーションサービス。"""

    def __init__(self, repository: PatientCoverageRepository) -> None:
        self._repository = repository

    async def read(self, query: GetPatientCoverageQuery) -> PatientCoverageDto:
        """法人境界を確認して患者資格DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        coverage_id = PatientCoverageId.parse(query.coverage_id)
        coverage = await load_coverage_or_raise(
            self._repository, corporate_id=corporate_id, coverage_id=coverage_id
        )
        return PatientCoverageDto.from_entity(coverage)
