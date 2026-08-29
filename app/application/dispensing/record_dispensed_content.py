"""調剤内容（変更調剤の3軸を含む）を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.application.dispensing.inputs import DispensedRpInput
from app.application.dispensing.reference import PrescriptionReferenceBoundary
from app.application.dispensing.support import (
    build_dispensed_rps,
    load_dispensing_or_raise,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensingConsistencyService,
    DispensingId,
    DispensingProcess,
    DispensingProcessRepository,
)


@dataclass(frozen=True, kw_only=True)
class RecordDispensedContentCommand:
    """調剤内容記録の入力データ。"""

    corporate_id: str
    dispensing_id: str
    dispensed_rps: tuple[DispensedRpInput, ...]


class RecordDispensedContentUseCase:
    """代替調剤・減数調剤・調製方法を含む調剤内容を差し替える。

    鑑査不合格による再調製もこのユースケースで行う。加算の算定可否は
    Claimの責務なので判定しない。
    """

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        prescription_reference: PrescriptionReferenceBoundary,
        consistency_service: DispensingConsistencyService,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._prescription_reference = prescription_reference
        self._consistency_service = consistency_service

    async def execute(
        self, command: RecordDispensedContentCommand
    ) -> DispensingProcessDto:
        """処方箋との整合を再確認してから調剤内容を保存する。

        変更制限に反する代替調剤は開始時だけでなく**変更のたびに**弾く。
        開始時だけの検証にすると、後から差し替えて回避できてしまう。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_DISPENSING,
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        process = process.update_dispensed_rps(
            build_dispensed_rps(command.dispensed_rps)
        )
        await self._verify_against_prescription(process)
        await self._repository.save(process)
        return DispensingProcessDto.from_entity(process)

    async def _verify_against_prescription(self, process: DispensingProcess) -> None:
        """処方箋との整合を検証する。

        調剤日・回数は開始時から変わらないので、前回セッションは取り直さない。
        """
        prescription = await self._prescription_reference.get_or_raise(
            corporate_id=process.corporate_id,
            prescription_id=process.prescription_id,
        )
        self._consistency_service.ensure_rps_match_prescription(process, prescription)
        self._consistency_service.ensure_substitutions_are_allowed(
            process, prescription
        )
