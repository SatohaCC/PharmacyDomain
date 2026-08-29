"""疑義照会を開始するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.prescription.get_prescription import PrescriptionDto
from app.application.prescription.reference import StaffQualificationBoundary
from app.application.prescription.support import (
    load_prescription_or_raise,
    parse_enum,
    required_text,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    InquiryCategory,
    InquiryContent,
    InquiryPharmacistService,
    InquiryTimestamp,
    PrescriptionId,
    PrescriptionRepository,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class StartInquiryCommand:
    """疑義照会開始の入力データ。照会日時は含めない。"""

    corporate_id: str
    prescription_id: str
    pharmacist_id: str
    category: str
    content: str


class StartInquiryUseCase:
    """実施者の薬剤師資格を確認して疑義照会を記録する。"""

    def __init__(
        self,
        repository: PrescriptionRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        pharmacist_service: InquiryPharmacistService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service
        self._clock = clock

    async def execute(self, command: StartInquiryCommand) -> PrescriptionDto:
        """薬剤師資格を確認し、注入Clock由来の日時で照会を追加する。

        照会日時をCommandで受け取らないのは AGENTS.md「資格の時間境界」と同じ理由で、
        呼び出し元が過去日時を詐称できないようにするため。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PRESCRIPTION,
        )
        prescription = await load_prescription_or_raise(
            self._repository,
            corporate_id=corporate_id,
            prescription_id=PrescriptionId.parse(command.prescription_id),
        )
        pharmacist_id = StaffId.parse(command.pharmacist_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=pharmacist_id,
        )
        self._pharmacist_service.ensure_pharmacist(qualifications)
        prescription = prescription.start_inquiry(
            pharmacist_id=pharmacist_id,
            category=parse_enum(InquiryCategory, command.category, "疑義照会区分"),
            content=InquiryContent(required_text(command.content, "疑義照会内容")),
            inquired_at=InquiryTimestamp(self._clock.now()),
        )
        await self._repository.save(prescription)
        return PrescriptionDto.from_entity(prescription)
