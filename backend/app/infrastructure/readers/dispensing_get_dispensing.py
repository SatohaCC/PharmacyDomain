"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.dispensing.interfaces.get_dispensing_query_reader import (
    GetDispensingQueryReader,
)
from app.application.dispensing.queries.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.queries.models import GetDispensingQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.infrastructure.readers.helpers.dispensing_support import (
    load_dispensing_or_raise,
)


class GetDispensingProjection(GetDispensingQueryReader):
    """法人境界を確認して調剤セッションを取得する。"""

    def __init__(self, repository: DispensingProcessRepository) -> None:
        self._repository = repository

    async def read(self, query: GetDispensingQuery) -> DispensingProcessDto:
        """指定法人の調剤セッションをDTOで返す。エンティティは返さない。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(query.dispensing_id),
        )
        return DispensingProcessDto.from_entity(process)
