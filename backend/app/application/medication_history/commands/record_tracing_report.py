"""Applicationのrecord_tracing_reportを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.medication_history.commands.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.commands.services.support import (
    load_record_or_raise,
    resolve_acting_pharmacist_id,
)
from app.application.medication_history.interfaces.references import (
    StaffQualificationBoundary,
)
from app.application.medication_history.values import parse_enum
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.entities import TracingReport
from app.domain.medication_history.identifiers import (
    MedicationHistoryRecordId,
    TracingReportId,
)
from app.domain.medication_history.primitives import (
    MedicalInstitutionName,
    PhysicianName,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportTimestamp,
)
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService


@dataclass(frozen=True, kw_only=True)
class RecordTracingReportCommand:
    """処方医への服薬情報等提供（トレーシングレポート）記録コマンド。"""

    corporate_id: str
    record_id: str
    provided_at: datetime
    medical_institution_name: str
    physician_name: str
    category: str
    fee_category: str
    delivery_method: str
    content: str
    reporter_id: str | None = None


class RecordTracingReportUseCase:
    """処方医への服薬情報等提供（トレーシングレポート）を記録する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._clock = clock

    async def execute(
        self, command: RecordTracingReportCommand
    ) -> MedicationHistoryDto:
        """トレーシングレポートを追加し、更新後の薬歴DTOを返す。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_MEDICATION_HISTORY
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        reporter_id = resolve_acting_pharmacist_id(
            self._corporate_access.actor, command.reporter_id
        )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=reporter_id,
            store_id=record.store_id,
            as_of=business_date(self._clock) if self._clock is not None else None,
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
        )
        updated_record = record.add_tracing_report(report)
        await self._repository.save(updated_record)
        return MedicationHistoryDto.from_entity(updated_record)
