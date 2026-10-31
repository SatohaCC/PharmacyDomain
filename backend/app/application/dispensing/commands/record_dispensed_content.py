"""Applicationのrecord_dispensed_contentを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.dispensing.commands.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.commands.models import DispensedRpInput
from app.application.dispensing.commands.services.support import (
    build_dispensed_rps,
    load_dispensing_or_raise,
    resolve_acting_staff_id,
)
from app.application.dispensing.interfaces.references import (
    PrescriptionReferenceBoundary,
    StaffQualificationBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingPharmacistService,
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
    請求算定側の責務なので判定しない。
    """

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        prescription_reference: PrescriptionReferenceBoundary,
        consistency_service: DispensingConsistencyService,
        staff_qualification: StaffQualificationBoundary | None = None,
        pharmacist_service: DispensingPharmacistService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._prescription_reference = prescription_reference
        self._consistency_service = consistency_service
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service
        self._clock = clock

    async def execute(
        self, command: RecordDispensedContentCommand
    ) -> DispensingProcessDto:
        """処方箋との整合を再確認してから調剤内容を保存する。

        変更制限に反する代替調剤は開始時だけでなく**変更のたびに**弾く。
        開始時だけの検証にすると、後から差し替えて回避できてしまう。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_DISPENSING
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        actor_staff_id = resolve_acting_staff_id(self._corporate_access.actor)
        if self._staff_qualification is not None:
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id,
                staff_id=actor_staff_id,
                store_id=process.store_id,
                as_of=business_date(self._clock) if self._clock is not None else None,
            )
            (
                self._pharmacist_service or DispensingPharmacistService()
            ).ensure_dispenser(qualifications)
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
            corporate_id=process.corporate_id, prescription_id=process.prescription_id
        )
        self._consistency_service.ensure_content_matches_prescription(
            process, prescription
        )
