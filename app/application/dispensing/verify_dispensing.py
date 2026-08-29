"""最終鑑査（調剤鑑査）の結果を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.application.dispensing.reference import StaffQualificationBoundary
from app.application.dispensing.support import (
    load_dispensing_or_raise,
    parse_enum,
    to_optional_text,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensingId,
    DispensingPharmacistService,
    DispensingProcessRepository,
    VerificationNotes,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class VerifyDispensingCommand:
    """最終鑑査記録の入力データ。鑑査日時は含めない。"""

    corporate_id: str
    dispensing_id: str
    verifier_id: str
    result: str
    notes: str | None = None


class VerifyDispensingUseCase:
    """鑑査者の資格を確認して最終鑑査の結果を記録する。"""

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        pharmacist_service: DispensingPharmacistService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service
        self._clock = clock

    async def execute(self, command: VerifyDispensingCommand) -> DispensingProcessDto:
        """薬剤師資格を確認し、注入Clock由来の日時で鑑査結果を記録する。

        調剤者本人が鑑査できないこと（一括代行署名の禁止）は集約が判定する。
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
        verifier_id = StaffId.parse(command.verifier_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=verifier_id,
        )
        self._pharmacist_service.ensure_verifier(qualifications)
        notes = to_optional_text(command.notes)
        process = process.verify(
            verifier_id=verifier_id,
            verified_at=VerificationTimestamp(self._clock.now()),
            result=parse_enum(VerificationResult, command.result, "鑑査結果"),
            notes=VerificationNotes(notes) if notes is not None else None,
        )
        await self._repository.save(process)
        return DispensingProcessDto.from_entity(process)
