"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.patient.errors import PatientExternalIdentifierNotFoundError
from app.application.patient.interfaces.get_patient_external_identifier_query_reader import (
    GetPatientExternalIdentifierQueryReader,
)
from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import GetPatientExternalIdentifierQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientExternalIdentifierId
from app.domain.patient.repositories import PatientExternalIdentifierRepository


class GetPatientExternalIdentifierProjection(GetPatientExternalIdentifierQueryReader):
    """外部患者ID対応付けを取得するアプリケーションサービス。"""

    def __init__(self, repository: PatientExternalIdentifierRepository) -> None:
        self._repository = repository

    async def read(
        self, query: GetPatientExternalIdentifierQuery
    ) -> PatientExternalIdentifierDto:
        """法人境界を確認して外部患者ID対応付けをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        identifier_id = PatientExternalIdentifierId.parse(query.identifier_id)
        identifier = await self._repository.get(
            corporate_id=corporate_id, identifier_id=identifier_id
        )
        if identifier is None:
            raise PatientExternalIdentifierNotFoundError()
        return PatientExternalIdentifierDto.from_entity(identifier)
