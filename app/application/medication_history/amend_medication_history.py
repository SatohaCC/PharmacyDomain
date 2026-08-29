"""確定済の薬歴へ修正を追記するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import SoapInput
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import (
    build_soap,
    load_record_or_raise,
    required_text,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    AmendmentReason,
    AmendmentTimestamp,
    CounselorQualificationService,
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class AmendMedicationHistoryCommand:
    """薬歴追記の入力データ。追記日時は含めない。"""

    corporate_id: str
    record_id: str
    amended_by: str
    reason: str
    amended_soap: SoapInput


class AmendMedicationHistoryUseCase:
    """確定済の薬歴に修正を追記する。

    元の記録は書き換えない。調剤録は3年間の保存義務があり、遡って
    書き換えられる記録は監査に耐えない。

    **追記しても頭書きへは再投影しない。** 追記は SOAP の修正であり、
    頭書きへの差分（``profile_updates``）は確定時に固定されている。
    追記で頭書きを動かせるようにすると、確定済薬歴から頭書きを再構築した
    結果と食い違う。
    """

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._clock = clock

    async def execute(
        self, command: AmendMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """追記者の薬剤師資格を確認し、注入Clock由来の日時で追記する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        amended_by = StaffId.parse(command.amended_by)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=amended_by
        )
        self._counselor_service.ensure_pharmacist(qualifications)
        record = record.amend(
            amended_soap=build_soap(command.amended_soap),
            reason=AmendmentReason(required_text(command.reason, "追記理由")),
            amended_by=amended_by,
            amended_at=AmendmentTimestamp(self._clock.now()),
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)
