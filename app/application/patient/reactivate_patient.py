"""患者再有効化ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.access_control.models import ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.lifecycle import PatientStatusReason
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class ReactivatePatientCommand:
    """患者再有効化の入力データ。"""

    corporate_id: str
    patient_id: str
    reason: str


class ReactivatePatientUseCase:
    """患者を再有効化するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ReactivatePatientCommand) -> None:
        """指定された患者を再有効化する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError(
                "患者状態の変更には本人とアカウントの特定が必要です。"
            )
        patient_id = PatientId.parse(command.patient_id)
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        now = self._clock.now()
        updated = patient.reactivate(
            reason=PatientStatusReason(command.reason),
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=now,
        )
        await self._repository.save(updated)
