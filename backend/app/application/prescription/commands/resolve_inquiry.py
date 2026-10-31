"""Applicationのresolve_inquiryを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.prescription.commands.dtos.get_prescription import PrescriptionDto
from app.application.prescription.commands.services.support import (
    load_prescription_or_raise,
    resolve_acting_pharmacist_id,
)
from app.application.prescription.interfaces.references import (
    StaffQualificationBoundary,
)
from app.application.prescription.values import parse_enum, required_text
from app.domain.corporate.identifiers import CorporateId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.primitives import (
    InquiryNumber,
    InquiryResponseContent,
    InquiryResultType,
    InquiryTimestamp,
    PrescriberName,
)
from app.domain.prescription.repositories import PrescriptionRepository
from app.domain.prescription.services import InquiryPharmacistService
from app.domain.prescription.value_objects import PrescriberResponse


@dataclass(frozen=True, kw_only=True)
class ResolveInquiryCommand:
    """疑義照会回答の入力データ。回答日時は含めない。"""

    corporate_id: str
    prescription_id: str
    inquiry_number: int
    responded_by: str
    result_type: str
    content: str


class ResolveInquiryUseCase:
    """疑義照会に回答を記録する。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
        staff_qualification: StaffQualificationBoundary | None = None,
        pharmacist_service: InquiryPharmacistService | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service

    async def execute(self, command: ResolveInquiryCommand) -> PrescriptionDto:
        """注入Clock由来の日時で回答を記録する。

        回答済みの照会への再回答は集約が拒否する（``InquiryAlreadyResolvedError``）。
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
        actor_staff_id = resolve_acting_pharmacist_id(self._corporate_access.actor)
        if self._staff_qualification is not None:
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id,
                staff_id=actor_staff_id,
                store_id=prescription.store_id,
                as_of=business_date(self._clock),
            )
            (self._pharmacist_service or InquiryPharmacistService()).ensure_pharmacist(
                qualifications
            )
        prescription = prescription.resolve_inquiry(
            inquiry_number=InquiryNumber(command.inquiry_number),
            response=PrescriberResponse(
                responded_by=PrescriberName(
                    required_text(command.responded_by, "回答医師氏名")
                ),
                responded_at=InquiryTimestamp(self._clock.now()),
                result_type=parse_enum(
                    InquiryResultType, command.result_type, "疑義照会結果区分"
                ),
                content=InquiryResponseContent(
                    required_text(command.content, "回答内容")
                ),
            ),
        )
        await self._repository.save(prescription)
        return PrescriptionDto.from_entity(prescription)
