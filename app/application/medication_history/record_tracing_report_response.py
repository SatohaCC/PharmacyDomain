"""トレーシングレポートに対する処方医返答記録ユースケース。"""

from __future__ import annotations

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common.optional_conversion import build_optional
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import RecordTracingReportResponseCommand
from app.application.medication_history.support import (
    load_record_or_raise,
    parse_enum,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
    PhysicianName,
    PrescriberActionType,
    TracingReportId,
    TracingReportResponse,
    TracingReportResponseContent,
    TracingReportTimestamp,
)
from app.domain.staff.primitives import StaffId


class RecordTracingReportResponseUseCase:
    """トレーシングレポートに対する処方医からの返答を記録する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: RecordTracingReportResponseCommand
    ) -> MedicationHistoryDto:
        """処方医返答を記録し、更新後の薬歴DTOを返す。"""
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

        response = TracingReportResponse(
            responded_at=TracingReportTimestamp(command.responded_at),
            content=TracingReportResponseContent(command.content),
            action_type=parse_enum(
                PrescriberActionType, command.action_type, "処方医の対応区分"
            ),
            received_by=StaffId.parse(command.received_by),
            acknowledged_physician_name=build_optional(
                command.acknowledged_physician_name, PhysicianName
            ),
        )

        updated_record = record.record_tracing_report_response(
            TracingReportId.parse(command.tracing_report_id), response
        )
        await self._repository.save(updated_record)
        return MedicationHistoryDto.from_entity(updated_record)
