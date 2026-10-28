"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.medication_history.interfaces.references import (
    DispensingReferenceBoundary,
    StatutoryRecordSourceBoundary,
)
from app.application.medication_history.interfaces.verify_statutory_record_query_reader import (
    VerifyStatutoryRecordQueryReader,
)
from app.application.medication_history.queries.dtos.verify_statutory_record import (
    StatutoryRecordSufficiencyDto,
)
from app.application.medication_history.queries.models import VerifyStatutoryRecordQuery
from app.application.medication_history.queries.services.statutory_projection import (
    StatutoryProjectionService,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.infrastructure.readers.helpers.medication_history_support import (
    load_record_or_raise,
)


class VerifyStatutoryRecordProjection(VerifyStatutoryRecordQueryReader):
    """薬歴が調剤録の記載事項を満たすかを確認する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        dispensing_source: DispensingReferenceBoundary,
        statutory_source: StatutoryRecordSourceBoundary,
        projection: StatutoryProjectionService,
    ) -> None:
        self._repository = repository
        self._dispensing_source = dispensing_source
        self._statutory_source = statutory_source
        self._projection = projection

    async def read(
        self, query: VerifyStatutoryRecordQuery
    ) -> StatutoryRecordSufficiencyDto:
        """指定法人の薬歴について、調剤録の代替可否をDTOで返す。

        確定済に限らない。足りないものを確定の前に知るための問い合わせでもある。

        氏名を問い合わせるのは調剤した薬剤師と指導した薬剤師の2人だけ。最終鑑査者は
        施行規則第16条第1項第五号の対象ではないので、ここでは尋ねない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        dispensing_id, prescription_id = self._projection.references(record)
        dispensing = await self._dispensing_source.get_or_raise(
            corporate_id=corporate_id, dispensing_id=dispensing_id
        )
        source = await self._statutory_source.build(
            corporate_id=corporate_id,
            patient_id=record.patient_id,
            prescription_id=prescription_id,
            staff_ids=self._projection.staff_ids(record, dispensing),
        )
        return self._projection.project(record, dispensing, source)
