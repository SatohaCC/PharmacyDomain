"""服薬期間中のフォローアップ追加ユースケース。"""

from __future__ import annotations

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import build_optional
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import AddFollowUpCommand
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import (
    build_handbook_status,
    build_profile_updates,
    build_residual_drug,
    build_soap,
    load_record_or_raise,
    parse_enum,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    FollowUpId,
    MajorCategoryCode,
    MedicationHistoryRecordId,
    MedicationHistorySourceSystem,
    MediumCategoryCode,
    StatutoryCategory,
)
from app.domain.medication_history.repository import (
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import (
    CategorizedNote,
    FollowUpRecord,
    ProfileUpdateIntents,
)
from app.domain.staff.primitives import StaffId


class AddFollowUpUseCase:
    """服薬期間中のフォローアップを記録する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        unit_of_work: UnitOfWork | None = None,
    ) -> None:
        self._repository = repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._unit_of_work = unit_of_work

    async def execute(self, command: AddFollowUpCommand) -> MedicationHistoryDto:
        """フォローアップを追加し、更新後の薬歴DTOを返す。"""
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

        counselor_id = StaffId.parse(command.counselor_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=counselor_id
        )
        self._counselor_service.ensure_pharmacist(qualifications)

        handbook_status = (
            build_handbook_status(command.handbook_status)
            if command.handbook_status is not None
            else None
        )
        residual_drug = (
            build_residual_drug(command.residual_drug)
            if command.residual_drug is not None
            else None
        )
        profile_updates = (
            build_profile_updates(command.profile_updates)
            if command.profile_updates is not None
            else ProfileUpdateIntents()
        )
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

        follow_up = FollowUpRecord(
            id=FollowUpId.generate(),
            counselor_id=counselor_id,
            followed_up_at=CounselingTimestamp(command.followed_up_at),
            method=(
                parse_enum(CounselingMethod, command.method, "フォローアップの方法")
                if command.method is not None
                else None
            ),
            soap=build_soap(command.soap),
            handbook_status=handbook_status,
            residual_drug=residual_drug,
            information_sheet_provided=command.information_sheet_provided,
            source_system=build_optional(
                command.source_system, MedicationHistorySourceSystem
            ),
            profile_updates=profile_updates,
            additional_notes=additional_notes,
        )

        updated_record = record.add_follow_up(follow_up)

        if not follow_up.profile_updates.is_empty:
            if self._unit_of_work is not None:
                self._unit_of_work.ensure_active()
            await self._repository.save(updated_record)
            profile = await self._profile_repository.get_by_patient(
                corporate_id=corporate_id,
                patient_id=record.patient_id,
            )
            if profile is None:
                profile = PatientMedicalProfile.empty_for(
                    corporate_id=corporate_id,
                    patient_id=record.patient_id,
                )
            updated_profile = profile.apply_follow_up(record, follow_up)
            await self._profile_repository.save(updated_profile)
        else:
            await self._repository.save(updated_record)

        return MedicationHistoryDto.from_entity(updated_record)
