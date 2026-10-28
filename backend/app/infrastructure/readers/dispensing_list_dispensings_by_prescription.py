"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.dispensing.interfaces.list_dispensings_by_prescription_query_reader import (
    ListDispensingsByPrescriptionQueryReader,
)
from app.application.dispensing.queries.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.queries.models import ListDispensingsByPrescriptionQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.prescription.identifiers import PrescriptionId


class ListDispensingsByPrescriptionProjection(ListDispensingsByPrescriptionQueryReader):
    """自局で実施した調剤セッションを調剤回数の昇順で返す。"""

    def __init__(self, repository: DispensingProcessRepository) -> None:
        self._repository = repository

    async def read(
        self, query: ListDispensingsByPrescriptionQuery
    ) -> tuple[DispensingProcessDto, ...]:
        """指定法人・処方箋の調剤セッションをDTOで返す。

        リフィル・分割の各回は別の保険薬局で行われうるため、**返る件数は
        その処方箋の総調剤回数と一致しない**。
        呼び出し側が件数から回数を導出してはならない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        processes = await self._repository.list_by_prescription(
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(query.prescription_id),
        )
        return tuple(DispensingProcessDto.from_entity(process) for process in processes)
