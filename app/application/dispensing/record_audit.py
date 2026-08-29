"""処方鑑査の結果を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.application.dispensing.reference import StaffQualificationBoundary
from app.application.dispensing.support import (
    load_dispensing_or_raise,
    to_optional_text,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    AuditNotes,
    AuditTimestamp,
    DispensingId,
    DispensingPharmacistService,
    DispensingProcessRepository,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class RecordAuditCommand:
    """処方鑑査記録の入力データ。鑑査日時は含めない。"""

    corporate_id: str
    dispensing_id: str
    auditor_id: str
    has_issues: bool
    notes: str | None = None


class RecordAuditUseCase:
    """調剤調製の前に行う処方鑑査（相互作用・重複投薬・用量）を記録する。

    調製された薬剤を確認する最終鑑査（``VerifyDispensingUseCase``）とは
    対象もタイミングも異なる。
    """

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

    async def execute(self, command: RecordAuditCommand) -> DispensingProcessDto:
        """鑑査者の薬剤師資格を確認し、注入Clock由来の日時で記録する。"""
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
        auditor_id = StaffId.parse(command.auditor_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=auditor_id,
        )
        self._pharmacist_service.ensure_auditor(qualifications)
        notes = to_optional_text(command.notes)
        process = process.record_audit(
            auditor_id=auditor_id,
            audited_at=AuditTimestamp(self._clock.now()),
            has_issues=command.has_issues,
            notes=AuditNotes(notes) if notes is not None else None,
        )
        await self._repository.save(process)
        return DispensingProcessDto.from_entity(process)
