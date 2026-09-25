"""患者氏名変更ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.patient.profile_history import record_manual_profile_change
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.shared.person_name import PersonNames


@dataclass(frozen=True, kw_only=True)
class ChangePatientNamesCommand:
    """患者氏名変更の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class ChangePatientNamesUseCase:
    """患者氏名を変更するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ChangePatientNamesCommand) -> None:
        """法人境界を確認して氏名変更とプロフィール履歴を保存する。"""
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
        names = PersonNames.create(
            last_name=command.last_name,
            first_name=command.first_name,
            last_name_kana=command.last_name_kana,
            first_name_kana=command.first_name_kana,
        )
        updated = patient.change_names(names)
        changed_fields = tuple(
            field
            for field, changed in (
                ("patient.kanji_name", patient.names.kanji != names.kanji),
                ("patient.kana_name", patient.names.kana != names.kana),
            )
            if changed
        )
        if not changed_fields:
            return
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError("患者プロフィールの変更には本人特定が必要です。")
        updated = record_manual_profile_change(
            before=patient,
            after=updated,
            changed_fields=changed_fields,
            actor=actor,
            recorded_at=self._clock.now(),
        )
        await self._repository.save(updated)
