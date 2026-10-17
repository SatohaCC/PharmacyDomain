"""患者プロフィール履歴のApplication変換。"""

from __future__ import annotations

from datetime import datetime

from app.application.access_control.models import ResolvedActorContext
from app.domain.patient.patient import Patient
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileChangeSource,
)


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
        changed_fields=changed_fields,
        before_profile=before.profile_snapshot(),
        applied_profile=after.profile_snapshot(),
        person_id=actor.person_id,
        account_id=actor.account_id,
    )
    return after.record_profile_change(change)
