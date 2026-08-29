"""疑義照会に処方医の回答を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common.clock import Clock
from app.application.prescription.get_prescription import PrescriptionDto
from app.application.prescription.support import (
    load_prescription_or_raise,
    parse_enum,
    required_text,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    InquiryNumber,
    InquiryResponseContent,
    InquiryResultType,
    InquiryTimestamp,
    PrescriberName,
    PrescriberResponse,
    PrescriptionId,
    PrescriptionRepository,
)


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
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ResolveInquiryCommand) -> PrescriptionDto:
        """注入Clock由来の日時で回答を記録する。

        回答済みの照会への再回答は集約が拒否する（``InquiryAlreadyResolvedError``）。
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
