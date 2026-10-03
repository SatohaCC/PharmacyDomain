"""薬歴事実の訂正を保存し、患者医療プロファイルを再構築する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.fact_value_conversion import (
    convert_fact_value,
)
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.profile_projection_service import (
    PatientMedicalProfileProjectionService,
)
from app.application.medication_history.reference import StaffQualificationBoundary
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
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
        organization_lock: OrganizationLock,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        category_catalog_repository: MedicationHistoryCategoryCatalogRepository,
        store_operations: StoreOperationBoundary,
        clock: Clock,
        projection_service: PatientMedicalProfileProjectionService | None = None,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._organization_lock = organization_lock
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._category_catalog_repository = category_catalog_repository
        self._store_operations = store_operations
        self._clock = clock
        self._projection_service = (
            projection_service
            or PatientMedicalProfileProjectionService(
                record_repository=record_repository,
                profile_repository=profile_repository,
            )
        )

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
        await self._organization_lock.acquire(
            f"medication-history-retention:{corporate_id.value}:{record.patient_id.value}"
        )
        # ロック待ちの間に別リクエストが同じ薬歴を更新した可能性があるため、
        # 患者単位ロックを得た後に対象も読み直す。
        record = await load_record_or_raise(
            self._record_repository,
            corporate_id=corporate_id,
            record_id=record.id,
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
        await self._projection_service.project(
            corporate_id=corrected.corporate_id,
            patient_id=corrected.patient_id,
        )
        return MedicationHistoryDto.from_entity(corrected)
