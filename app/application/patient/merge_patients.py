"""患者名寄せ統合ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.lifecycle import PatientStatusReason
from app.domain.patient.merge_service import PatientMergeService
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class MergePatientsCommand:
    """患者名寄せ統合の入力データ。"""

    corporate_id: str
    source_patient_id: str
    target_patient_id: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class MergePatientsResultDto:
    """患者名寄せ統合の完了DTO。"""

    source_patient_id: str
    target_patient_id: str
    merged_at: datetime


class MergePatientsUseCase:
    """患者を名寄せ統合するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: MergePatientsCommand) -> MergePatientsResultDto:
        """source患者をtarget患者へ名寄せ統合する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError(
                "患者名寄せ統合には本人とアカウントの特定が必要です。"
            )
        source_id = PatientId.parse(command.source_patient_id)
        target_id = PatientId.parse(command.target_patient_id)
        source = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=source_id,
        )
        target = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=target_id,
        )
        now = self._clock.now()
        merged_source = PatientMergeService.merge(
            source,
            target,
            reason=PatientStatusReason(command.reason),
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=now,
        )
        await self._repository.save(merged_source)
        return MergePatientsResultDto(
            source_patient_id=str(merged_source.id.value),
            target_patient_id=str(target.id.value),
            merged_at=now,
        )
