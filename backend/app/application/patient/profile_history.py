"""患者プロフィール履歴のApplication変換。"""

from __future__ import annotations

from datetime import datetime

from app.application.access_control.models import ResolvedActorContext
from app.domain.patient.entities import Patient
from app.domain.patient.primitives import (
    PatientProfileChangeSource,
    PatientProfileField,
)
from app.domain.patient.value_objects import PatientProfileChange


def record_manual_profile_change(
    *,
    before: Patient,
    after: Patient,
    changed_fields: tuple[str, ...],
    actor: ResolvedActorContext,
    recorded_at: datetime,
) -> Patient:
    """手動変更の出所・前後Snapshot・認証済みActorを追記する。"""
    change = PatientProfileChange(
        source=PatientProfileChangeSource.MANUAL,
        recorded_at=recorded_at,
        changed_fields=tuple(PatientProfileField(item) for item in changed_fields),
        before_profile=before.profile_snapshot(),
        applied_profile=after.profile_snapshot(),
        person_id=actor.person_id,
        account_id=actor.account_id,
    )
    return after.record_profile_change(change)
