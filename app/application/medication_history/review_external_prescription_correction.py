"""外部処方訂正レビューの公開インターフェース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import SoapInput
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import (
    build_soap,
    load_record_or_raise,
    parse_enum,
    required_text,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    MedicationHistoryNotFinalizedError,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import (
    ExternalCorrectionDecision,
)
from app.domain.prescription.primitives import PrescriptionId
from app.domain.prescription.repository import PrescriptionRepository


@dataclass(frozen=True, kw_only=True)
class ReviewExternalPrescriptionCorrectionCommand:
    """外部訂正への判断入力。監査担当者と記録時刻は含めない。"""

    corporate_id: str
    record_id: str
    correction_id: str
    decision: str
    reason: str
    amended_soap: SoapInput | None = None
    matched_prescription_id: str | None = None


class ReviewExternalPrescriptionCorrectionUseCase:
    """信頼済み薬剤師ActorとClockで外部訂正を判断・保存する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        prescription_repository: PrescriptionRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._prescription_repository = prescription_repository
        self._clock = clock
        self._counselor_service = CounselorQualificationService()

    async def execute(
        self, command: ReviewExternalPrescriptionCorrectionCommand
    ) -> MedicationHistoryDto:
        """認可と資格を検証し、薬歴集約を一度だけ保存する。"""
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
        AuthorizationService(self._corporate_access.actor).require_store(
            permission=Permission.MANAGE_MEDICATION_HISTORY,
            target_corporate_id=corporate_id,
            target_store_id=record.store_id,
        )
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
            raise AuthorizationError(
                "外部訂正の判断にはスタッフを特定できるActorが必要です。"
            )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=actor.staff_id
        )
        self._counselor_service.ensure_pharmacist(qualifications)
        if not record.is_finalized:
            raise MedicationHistoryNotFinalizedError()

        decision = parse_enum(
            ExternalCorrectionDecision, command.decision, "外部訂正の判断"
        )
        matched_id = (
            PrescriptionId.parse(command.matched_prescription_id)
            if command.matched_prescription_id is not None
            else None
        )
        if (
            decision is ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
            and matched_id is not None
        ):
            matched_prescription = await self._prescription_repository.get(
                corporate_id=corporate_id,
                prescription_id=matched_id,
            )
            if (
                matched_prescription is None
                or matched_prescription.patient_id != record.patient_id
            ):
                raise NotFoundError(
                    "照合先の処方箋が同一法人・患者の記録として見つかりません。"
                )
        reviewed = record.review_external_correction(
            correction_id=command.correction_id,
            decision=decision,
            reason=required_text(command.reason, "判断理由"),
            reviewed_by=actor.staff_id,
            reviewed_at=ExternalCorrectionTimestamp(self._clock.now()),
            amended_soap=(
                build_soap(command.amended_soap)
                if command.amended_soap is not None
                else None
            ),
            matched_prescription_id=matched_id,
        )
        await self._repository.save(reviewed)
        return MedicationHistoryDto.from_entity(reviewed)
