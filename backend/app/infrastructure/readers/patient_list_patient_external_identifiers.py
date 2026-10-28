"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.patient.interfaces.list_patient_external_identifiers_query_reader import (
    ListPatientExternalIdentifiersQueryReader,
)
from app.application.patient.queries.dtos.register_patient_external_identifier import (
    PatientExternalIdentifierDto,
)
from app.application.patient.queries.models import ListPatientExternalIdentifiersQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)
from app.infrastructure.readers.helpers.patient_support import load_patient_or_raise


class ListPatientExternalIdentifiersProjection(
    ListPatientExternalIdentifiersQueryReader
):
    """患者に紐付く外部患者ID一覧を取得する。"""

    def __init__(
        self,
        patient_repository: PatientRepository,
        identifier_repository: PatientExternalIdentifierRepository,
    ) -> None:
        self._patient_repository = patient_repository
        self._identifier_repository = identifier_repository

    async def read(
        self, query: ListPatientExternalIdentifiersQuery
    ) -> list[PatientExternalIdentifierDto]:
        """法人境界と患者の存在を確認して外部患者ID一覧を返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        patient_id = PatientId.parse(query.patient_id)
        await load_patient_or_raise(
            self._patient_repository, corporate_id=corporate_id, patient_id=patient_id
        )
        identifiers = await self._identifier_repository.list_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return [PatientExternalIdentifierDto.from_entity(item) for item in identifiers]
