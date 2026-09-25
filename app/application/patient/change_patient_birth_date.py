"""患者生年月日変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.patient.profile_history import record_manual_profile_change
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientBirthDate, PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class ChangePatientBirthDateCommand:
    """患者生年月日変更の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    birth_date: date | None


class ChangePatientBirthDateUseCase:
    """患者の生年月日を変更するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ChangePatientBirthDateCommand) -> None:
        """法人境界を確認して生年月日の変更と履歴を保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        patient_id = PatientId.parse(command.patient_id)
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        birth_date = (
            PatientBirthDate(command.birth_date) if command.birth_date else None
        )
        updated = patient.change_birth_date(birth_date)
        if patient.birth_date == birth_date:
            return
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError("患者プロフィールの変更には本人特定が必要です。")
        updated = record_manual_profile_change(
            before=patient,
            after=updated,
            changed_fields=("patient.birth_date",),
            actor=actor,
            recorded_at=self._clock.now(),
        )
        await self._repository.save(updated)
