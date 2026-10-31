"""Applicationのreview_external_prescription_correctionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import NotFoundError
from app.application.medication_history.commands.dtos.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.commands.models import SoapInput
from app.application.medication_history.commands.services.support import (
    build_soap,
    load_record_or_raise,
    resolve_acting_pharmacist_id,
)
from app.application.medication_history.interfaces.references import (
    StaffQualificationBoundary,
)
from app.application.medication_history.values import parse_enum, required_text
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import MedicationHistoryNotFinalizedError
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.primitives import (
    ExternalCorrectionDecision,
    ExternalCorrectionTimestamp,
)
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository


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
            corporate_id=corporate_id, permission=Permission.MANAGE_MEDICATION_HISTORY
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
        reviewer_id = resolve_acting_pharmacist_id(
            self._corporate_access.actor,
            error_message="外部訂正の判断にはスタッフを特定できるActorが必要です。",
        )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=reviewer_id,
            store_id=record.store_id,
            as_of=business_date(self._clock),
        )
        self._counselor_service.ensure_pharmacist(qualifications)
        decision = parse_enum(
            ExternalCorrectionDecision, command.decision, "外部訂正の判断"
        )
        if not record.is_finalized and decision not in (
            ExternalCorrectionDecision.NO_ACTION,
            ExternalCorrectionDecision.INVESTIGATING,
        ):
            raise MedicationHistoryNotFinalizedError()
        if decision in (
            ExternalCorrectionDecision.NO_ACTION,
            ExternalCorrectionDecision.INVESTIGATING,
        ) and (
            command.amended_soap is not None
            or command.matched_prescription_id is not None
        ):
            raise DomainValidationError(
                "確認または調査中の判断には追記SOAPや照合処方を指定できません。"
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
                corporate_id=corporate_id, prescription_id=matched_id
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
            reviewed_by=reviewer_id,
            reviewed_at=ExternalCorrectionTimestamp(self._clock.now()),
            amended_soap=build_soap(command.amended_soap)
            if command.amended_soap is not None
            else None,
            matched_prescription_id=matched_id,
        )
        await self._repository.save(reviewed)
        return MedicationHistoryDto.from_entity(reviewed)
