"""処方医への服薬情報等提供（トレーシングレポート）記録ユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import build_optional
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import RecordTracingReportCommand
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import (
    load_record_or_raise,
    parse_enum,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import (
    FollowUpId,
    MedicationHistoryRecordId,
    PhysicianName,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportId,
    TracingReportTimestamp,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import TracingReport
from app.domain.prescription.primitives import MedicalInstitutionName
from app.domain.staff.primitives import StaffId


class RecordTracingReportUseCase:
    """処方医への服薬情報等提供（トレーシングレポート）を記録する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service

    async def execute(
        self, command: RecordTracingReportCommand
    ) -> MedicationHistoryDto:
        """トレーシングレポートを追加し、更新後の薬歴DTOを返す。"""
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

        reporter_id = StaffId.parse(command.reporter_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=reporter_id
        )
        self._counselor_service.ensure_pharmacist(qualifications)

        report = TracingReport(
            id=TracingReportId.generate(),
            reporter_id=reporter_id,
            provided_at=TracingReportTimestamp(command.provided_at),
            medical_institution_name=MedicalInstitutionName(
                command.medical_institution_name
            ),
            physician_name=PhysicianName(command.physician_name),
            category=parse_enum(
                TracingReportCategory,
                command.category,
                "トレーシングレポートの提供区分",
            ),
            fee_category=parse_enum(
                TracingReportFeeCategory,
                command.fee_category,
                "トレーシングレポートの算定区分",
            ),
            delivery_method=parse_enum(
                TracingReportDeliveryMethod,
                command.delivery_method,
                "トレーシングレポートの提供手段",
            ),
            content=TracingReportContent(command.content),
            follow_up_id=build_optional(command.follow_up_id, FollowUpId.parse),
        )

        updated_record = record.add_tracing_report(report)
        await self._repository.save(updated_record)
        return MedicationHistoryDto.from_entity(updated_record)
