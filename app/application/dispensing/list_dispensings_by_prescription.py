"""処方箋に紐付く調剤セッションを一覧するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import DispensingProcessRepository
from app.domain.prescription.primitives import PrescriptionId


@dataclass(frozen=True, kw_only=True)
class ListDispensingsByPrescriptionQuery:
    """調剤セッション一覧取得の入力データ。"""

    corporate_id: str
    prescription_id: str


class ListDispensingsByPrescriptionUseCase:
    """自局で実施した調剤セッションを調剤回数の昇順で返す。"""

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListDispensingsByPrescriptionQuery
    ) -> tuple[DispensingProcessDto, ...]:
        """指定法人・処方箋の調剤セッションをDTOで返す。

        リフィル・分割の各回は別の保険薬局で行われうるため、**返る件数は
        その処方箋の総調剤回数と一致しない**。
        呼び出し側が件数から回数を導出してはならない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_DISPENSING,
        )
        processes = await self._repository.list_by_prescription(
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(query.prescription_id),
        )
        return tuple(DispensingProcessDto.from_entity(process) for process in processes)
