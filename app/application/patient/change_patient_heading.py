"""患者頭書きの更新契約。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import build_optional
from app.application.patient.get_patient_heading import PatientHeadingDto, _to_dto
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.heading import PatientHeadingContent, PatientHeadingText
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class ChangePatientHeadingCommand:
    """患者頭書きの部分更新入力。"""

    corporate_id: str
    patient_id: str
    expected_revision: int
    provided_fields: frozenset[str]
    summary: str | None = None
    notes: str | None = None


class ChangePatientHeadingUseCase:
    """本人・適用時刻・改訂を検証して患者頭書きを更新する契約。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ChangePatientHeadingCommand) -> PatientHeadingDto:
        """患者の現在値を保ちながら指定欄を追記更新する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT_HEADING,
        )
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=PatientId.parse(command.patient_id),
        )
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT_HEADING,
        )
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext):
            raise AuthorizationError("患者頭書きの変更には本人特定が必要です。")
        if type(command.expected_revision) is not int or command.expected_revision < 0:
            raise DomainValidationError("期待改訂は0以上の整数で指定してください。")
        allowed_fields = frozenset({"summary", "notes"})
        if command.provided_fields - allowed_fields:
            raise DomainValidationError("変更できない患者頭書き項目があります。")
        if not command.provided_fields:
            raise DomainValidationError("変更する患者頭書き項目を指定してください。")
        current = (
            patient.heading_history[-1].content
            if patient.heading_history
            else PatientHeadingContent(summary=None, notes=None)
        )
        content = PatientHeadingContent(
            summary=(
                build_optional(command.summary, PatientHeadingText)
                if "summary" in command.provided_fields
                else current.summary
            ),
            notes=(
                build_optional(command.notes, PatientHeadingText)
                if "notes" in command.provided_fields
                else current.notes
            ),
        )
        updated = patient.change_heading(
            content,
            expected_revision=command.expected_revision,
            person_id=actor.person_id,
            account_id=actor.account_id,
            recorded_at=self._clock.now(),
        )
        if updated is not patient:
            await self._repository.save(updated)
        return _to_dto(str(updated.id.value), updated.heading_history)
