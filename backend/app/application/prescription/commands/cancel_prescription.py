"""Applicationのcancel_prescriptionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.prescription.commands.dtos.get_prescription import PrescriptionDto
from app.application.prescription.commands.services.support import (
    load_prescription_or_raise,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository


@dataclass(frozen=True, kw_only=True)
class CancelPrescriptionCommand:
    """処方箋取消の入力データ。"""

    corporate_id: str
    prescription_id: str


class CancelPrescriptionUseCase:
    """処方箋を取消・無効にする。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: CancelPrescriptionCommand) -> PrescriptionDto:
        """終端状態からの取消は集約の遷移表が拒否する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_PRESCRIPTION
        )
        prescription = await load_prescription_or_raise(
            self._repository,
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(command.prescription_id),
        )
        prescription = prescription.cancel()
        await self._repository.save(prescription)
        return PrescriptionDto.from_entity(prescription)
