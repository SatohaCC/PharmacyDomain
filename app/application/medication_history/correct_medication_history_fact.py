"""薬歴事実の訂正を保存し、患者医療プロファイルを再構築する。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.fact_value_conversion import (
    convert_fact_value,
)
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.repository import (
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.staff.primitives import StaffId

_VALUE_ABSENT = object()


@dataclass(frozen=True, kw_only=True)
class CorrectMedicationHistoryFactCommand:
    """訂正対象、操作、理由と新しい値。監査値は含めない。"""

    corporate_id: str
    record_id: str
    target: str
    operation: str
    reason: str
    value: object = _VALUE_ABSENT


class CorrectMedicationHistoryFactUseCase:
    """確定済み薬歴へ事実訂正を追記し、同じ業務単位で頭書きを再投影する。"""

    def __init__(
        self,
        *,
        record_repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        category_catalog_repository: MedicationHistoryCategoryCatalogRepository,
        store_operations: StoreOperationBoundary,
        clock: Clock,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._category_catalog_repository = category_catalog_repository
        self._store_operations = store_operations
        self._clock = clock

    async def execute(
        self, command: CorrectMedicationHistoryFactCommand
    ) -> MedicationHistoryDto:
        """Actorと店舗を検証し、薬歴を先に保存してから頭書きを再構築する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._record_repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=record.store_id,
            operation=StoreOperation.AMEND_HISTORY,
        )
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
            raise AuthorizationError(
                "薬歴訂正にはスタッフを特定できるActorが必要です。"
            )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=actor.staff_id
        )
        self._counselor_service.ensure_pharmacist(qualifications)
        raw_value = command.value
        if raw_value is _VALUE_ABSENT:
            corrected = record.correct_fact(
                target=command.target,
                operation=command.operation,
                reason=command.reason,
                corrected_by=actor.staff_id,
                recorded_at=self._clock.now(),
            )
        else:
            value = convert_fact_value(record, target=command.target, raw=raw_value)
            if command.target == "counselor_id" and value is not None:
                counselor_id = value
                if not isinstance(counselor_id, StaffId):
                    raise AuthorizationError("訂正先の指導者が正しくありません。")
                target_qualifications = (
                    await self._staff_qualification.get_qualifications(
                        corporate_id=corporate_id, staff_id=counselor_id
                    )
                )
                self._counselor_service.ensure_pharmacist(target_qualifications)
            corrected = record.correct_fact(
                target=command.target,
                operation=command.operation,
                reason=command.reason,
                corrected_by=actor.staff_id,
                recorded_at=self._clock.now(),
                value=value,
            )
        catalog = await self._category_catalog_repository.get(corporate_id=corporate_id)
        if catalog is not None:
            catalog.validate_record_compliance(corrected)
        await self._record_repository.save(corrected)
        await self._rebuild_profile(corrected)
        return MedicationHistoryDto.from_entity(corrected)

    async def _rebuild_profile(self, record: MedicationHistoryRecord) -> None:
        """患者の全店舗の薬歴を再生し、既存の頭書きIDを維持する。"""
        records = await self._record_repository.list_for_profile_projection(
            corporate_id=record.corporate_id, patient_id=record.patient_id
        )
        rebuilt = PatientMedicalProfile.rebuild_from(
            corporate_id=record.corporate_id,
            patient_id=record.patient_id,
            records=tuple(item for item in records if item.is_projection_eligible),
        )
        existing = await self._profile_repository.get_by_patient(
            corporate_id=record.corporate_id, patient_id=record.patient_id
        )
        if existing is not None:
            rebuilt = replace(rebuilt, id=existing.id)
        await self._profile_repository.save(rebuilt)
