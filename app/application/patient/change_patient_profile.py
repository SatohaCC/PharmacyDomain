"""受付外の患者プロフィール変更の入力と実行契約。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import build_optional
from app.application.patient.profile_history import record_manual_profile_change
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.primitives import (
    PatientAddress,
    PatientGenderCode,
    PatientId,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.repository import PatientRepository

_PROFILE_FIELDS = (
    "gender",
    "postal_code",
    "address",
    "phone_number",
)


@dataclass(frozen=True, kw_only=True)
class ChangePatientProfileCommand:
    """PATCHで指定された患者プロフィール項目。"""

    corporate_id: str
    patient_id: str
    provided_fields: frozenset[str]
    gender: str | None = None
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None


class ChangePatientProfileUseCase:
    """受付外の連絡先・性別変更を記録するUseCase契約。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._clock = clock

    async def execute(self, command: ChangePatientProfileCommand) -> None:
        """認可した更新値と変更履歴を保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PATIENT,
        )
        unsupported = command.provided_fields - frozenset(_PROFILE_FIELDS)
        if unsupported:
            raise DomainValidationError("変更できない患者プロフィール項目があります。")
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=PatientId.parse(command.patient_id),
        )
        before = patient.profile_snapshot()
        gender = (
            build_optional(command.gender, PatientGenderCode)
            if "gender" in command.provided_fields
            else before.gender
        )
        postal_code = (
            build_optional(command.postal_code, PatientPostalCode)
            if "postal_code" in command.provided_fields
            else before.postal_code
        )
        address = (
            build_optional(command.address, PatientAddress)
            if "address" in command.provided_fields
            else before.address
        )
        phone_number = (
            build_optional(command.phone_number, PatientPhoneNumber)
            if "phone_number" in command.provided_fields
            else before.phone_number
        )
        changed_fields = tuple(
            f"patient.{field}"
            for field, old_value, new_value in (
                ("gender", before.gender, gender),
                ("postal_code", before.postal_code, postal_code),
                ("address", before.address, address),
                ("phone_number", before.phone_number, phone_number),
            )
            if field in command.provided_fields and old_value != new_value
        )
        if not changed_fields:
            return
        after_profile = replace(
            before,
            gender=gender,
            postal_code=postal_code,
            address=address,
            phone_number=phone_number,
        )
        updated = patient.change_profile(after_profile)
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
