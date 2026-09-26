"""店舗をまたぐ独立フォローアップ薬歴を起票するユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import build_optional
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.exceptions import MedicationHistoryNotFoundError
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import AddFollowUpCommand
from app.application.medication_history.reference import (
    MedicationHistoryFollowUpSourceBoundary,
    StaffQualificationBoundary,
)
from app.application.medication_history.support import (
    build_handbook_status,
    build_profile_updates,
    build_residual_drug,
    build_soap,
    parse_enum,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    MedicationHistoryDomainError,
    SoapContentRequiredError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    FollowUpRecordedTimestamp,
    MajorCategoryCode,
    MedicationHistoryRecordId,
    MedicationHistoryRecordKind,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
    MediumCategoryCode,
    StatutoryCategory,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import CategorizedNote
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


class AddFollowUpUseCase:
    """確定済み薬歴のメタデータを根拠に別店舗の新規薬歴を作る。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        unit_of_work: UnitOfWork,
        store_operations: StoreOperationBoundary,
        source_boundary: MedicationHistoryFollowUpSourceBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._unit_of_work = unit_of_work
        self._store_operations = store_operations
        self._source_boundary = source_boundary
        self._clock = clock

    async def execute(self, command: AddFollowUpCommand) -> MedicationHistoryDto:
        """参照元を本文ごと読み込まず、独立した下書きを保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        patient_id = PatientId.parse(command.patient_id)
        store_id = StoreId.parse(command.store_id)
        actor = self._corporate_access.actor
        self._unit_of_work.ensure_active()
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        authorization = AuthorizationService(actor)
        authorization.require_store(
            permission=Permission.MANAGE_MEDICATION_HISTORY,
            target_corporate_id=corporate_id,
            target_store_id=store_id,
        )
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.START_HISTORY,
        )

        source = await self._source_boundary.get_source_reference(
            corporate_id=corporate_id,
            patient_id=patient_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        if source is None:
            raise MedicationHistoryNotFoundError()
        if source.status is not MedicationHistoryStatus.FINALIZED:
            try:
                authorization.require_store(
                    permission=Permission.VIEW_MEDICATION_HISTORY,
                    target_corporate_id=corporate_id,
                    target_store_id=source.store_id,
                )
            except (AuthorizationError, TenantBoundaryNotFoundError) as error:
                raise MedicationHistoryNotFoundError() from error
            raise MedicationHistoryDomainError(
                "未確定の薬歴はフォローアップの参照元にできません。"
            )
        if source.patient_id != patient_id or source.corporate_id != corporate_id:
            raise MedicationHistoryNotFoundError()
        if source.counseled_at is None:
            raise MedicationHistoryNotFoundError()
        followed_up_at = CounselingTimestamp(command.followed_up_at)
        if followed_up_at.value <= source.counseled_at:
            raise MedicationHistoryDomainError(
                "フォローアップの指導日時は参照元の指導日時より後にしてください。"
            )

        if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
            raise AuthorizationError(
                "フォローアップの記載者をスタッフとして特定できません。"
            )
        recorded_by = actor.staff_id
        recorded_qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=recorded_by,
        )
        self._counselor_service.ensure_pharmacist(recorded_qualifications)

        counselor_id = StaffId.parse(command.counselor_id)
        counselor_qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=counselor_id,
        )
        self._counselor_service.ensure_pharmacist(counselor_qualifications)

        soap = build_soap(command.soap)
        additional_notes = tuple(
            CategorizedNote(
                major_category_code=MajorCategoryCode(note.major_category_code),
                medium_category_code=MediumCategoryCode(note.medium_category_code),
                text=CounselingNote(note.text),
                statutory_category=parse_enum(
                    StatutoryCategory, note.category, "記載メモの法定区分"
                ),
            )
            for note in command.additional_notes
        )
        if not soap.has_content and not any(
            note.has_content for note in additional_notes
        ):
            raise SoapContentRequiredError()
        recorded_at = FollowUpRecordedTimestamp(self._clock.now())

        record = MedicationHistoryRecord.start(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=source.patient_id,
            dispensing_id=source.dispensing_id,
            prescription_id=source.prescription_id,
            counselor_id=counselor_id,
            counseled_at=followed_up_at,
            method=(
                parse_enum(CounselingMethod, command.method, "服薬指導の方法")
                if command.method is not None
                else None
            ),
            soap=soap,
            handbook_status=(
                build_handbook_status(command.handbook_status)
                if command.handbook_status is not None
                else None
            ),
            residual_drug=(
                build_residual_drug(command.residual_drug)
                if command.residual_drug is not None
                else None
            ),
            information_sheet_provided=command.information_sheet_provided,
            profile_updates=build_profile_updates(command.profile_updates),
            additional_notes=additional_notes,
            source_system=build_optional(
                command.source_system, MedicationHistorySourceSystem
            ),
            recorded_by=recorded_by,
            recorded_at=recorded_at,
            record_kind=MedicationHistoryRecordKind.FOLLOW_UP,
            source_record_id=source.record_id,
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)


__all__ = ["AddFollowUpUseCase"]
