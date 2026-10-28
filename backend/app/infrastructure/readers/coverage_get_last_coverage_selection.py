"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.coverage.interfaces.get_last_coverage_selection_query_reader import (
    GetLastCoverageSelectionQueryReader,
)
from app.application.coverage.interfaces.references import (
    CoverageValidityBoundary,
)
from app.application.coverage.queries.dtos.get_coverage_selection import (
    CoverageSelectionRecordDto,
)
from app.application.coverage.queries.dtos.get_last_coverage_selection import (
    LastCoverageSelectionCandidateDto,
)
from app.application.coverage.queries.models import GetLastCoverageSelectionQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.primitives import CoverageAppliedOn
from app.domain.coverage.repositories import CoverageSelectionRecordRepository
from app.domain.patient.identifiers import PatientId
from app.domain.store.identifiers import StoreId


class GetLastCoverageSelectionProjection(GetLastCoverageSelectionQueryReader):
    """最新履歴を再検証済みの初期候補として返す。"""

    def __init__(
        self,
        repository: CoverageSelectionRecordRepository,
        coverage_validity: CoverageValidityBoundary,
    ) -> None:
        self._repository = repository
        self._coverage_validity = coverage_validity

    async def read(
        self, query: GetLastCoverageSelectionQuery
    ) -> LastCoverageSelectionCandidateDto | None:
        """最新履歴があれば元IDと値を今回の適用日で再検証して返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        patient_id = PatientId.parse(query.patient_id)
        record = await self._repository.get_latest(
            corporate_id=corporate_id, store_id=store_id, patient_id=patient_id
        )
        if record is None:
            return None
        is_still_valid = await self._coverage_validity.is_selection_valid(
            corporate_id=corporate_id,
            patient_id=patient_id,
            selection=record.selection,
            applied_on=CoverageAppliedOn(query.applied_on),
        )
        return LastCoverageSelectionCandidateDto(
            record=CoverageSelectionRecordDto.from_entity(record),
            is_still_valid=is_still_valid,
        )
