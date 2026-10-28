"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.prescription.interfaces.get_prescription_query_reader import (
    GetPrescriptionQueryReader,
)
from app.application.prescription.queries.dtos.get_prescription import PrescriptionDto
from app.application.prescription.queries.models import GetPrescriptionQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository
from app.infrastructure.readers.helpers.prescription_support import (
    load_prescription_or_raise,
)


class GetPrescriptionProjection(GetPrescriptionQueryReader):
    """法人境界を確認して処方箋を取得する。"""

    def __init__(self, repository: PrescriptionRepository) -> None:
        self._repository = repository

    async def read(self, query: GetPrescriptionQuery) -> PrescriptionDto:
        """指定法人の処方箋をDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        prescription = await load_prescription_or_raise(
            self._repository,
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(query.prescription_id),
        )
        return PrescriptionDto.from_entity(prescription)
