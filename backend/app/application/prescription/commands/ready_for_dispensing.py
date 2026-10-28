"""Applicationのready_for_dispensingを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.prescription.commands.dtos.get_prescription import PrescriptionDto
from app.application.prescription.commands.models import ReadyForDispensingCommand
from app.application.prescription.commands.services.support import (
    load_prescription_or_raise,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository


class ReadyForDispensingUseCase:
    """処方箋を調剤可能な状態へ進める。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: ReadyForDispensingCommand) -> PrescriptionDto:
        """未回答の疑義照会が無いことを集約に確認させてから状態を進める。

        「未回答の照会があるか」は集約が単独で判定できるため、ここでは
        判定を重複させない（AGENTS.md「単一集約で完結する不変条件を
        Domain Service 側にも重複して置かない」と同じ理由）。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_PRESCRIPTION
        )
        prescription = await load_prescription_or_raise(
            self._repository,
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(command.prescription_id),
        )
        prescription = prescription.ready_for_dispensing()
        await self._repository.save(prescription)
        return PrescriptionDto.from_entity(prescription)
