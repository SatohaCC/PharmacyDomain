"""Applicationのverify_statutory_recordを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.medication_history.interfaces.verify_statutory_record_query_reader import (
    VerifyStatutoryRecordQueryReader,
)
from app.application.medication_history.queries.dtos.verify_statutory_record import (
    StatutoryRecordSufficiencyDto,
)
from app.application.medication_history.queries.models import VerifyStatutoryRecordQuery
from app.domain.corporate.identifiers import CorporateId


class VerifyStatutoryRecordUseCase:
    def __init__(
        self,
        reader: VerifyStatutoryRecordQueryReader,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._reader = reader
        self._corporate_access = corporate_access

    async def execute(
        self, query: VerifyStatutoryRecordQuery
    ) -> StatutoryRecordSufficiencyDto:
        """指定法人の薬歴について、調剤録の代替可否をDTOで返す。

        確定済に限らない。足りないものを確定の前に知るための問い合わせでもある。

        氏名を問い合わせるのは調剤した薬剤師と指導した薬剤師の2人だけ。最終鑑査者は
        施行規則第16条第1項第五号の対象ではないので、ここでは尋ねない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.VIEW_MEDICATION_HISTORY
        )
        return await self._reader.read(query)
