"""Applicationのget_patient_headingを定義する。"""

from __future__ import annotations

from app.application.common.optional_conversion import unwrap
from app.application.patient.commands.dtos.get_patient_heading import (
    PatientHeadingDto,
    PatientHeadingRevisionDto,
)
from app.domain.patient.value_objects import PatientHeadingRevision


def _to_dto(
    patient_id: str, revisions: tuple[PatientHeadingRevision, ...]
) -> PatientHeadingDto:
    """履歴から頭書きの現在値と改訂一覧を組み立てる。"""
    history = tuple(
        (
            PatientHeadingRevisionDto(
                revision=index,
                summary=unwrap(revision.content.summary),
                notes=unwrap(revision.content.notes),
                person_id=str(revision.person_id.value),
                account_id=str(revision.account_id.value),
                recorded_at=revision.recorded_at.value.isoformat(),
            )
            for index, revision in enumerate(revisions, start=1)
        )
    )
    latest = revisions[-1] if revisions else None
    return PatientHeadingDto(
        patient_id=patient_id,
        revision=len(revisions),
        summary=unwrap(latest.content.summary) if latest is not None else None,
        notes=unwrap(latest.content.notes) if latest is not None else None,
        updated_by_person_id=str(latest.person_id.value)
        if latest is not None
        else None,
        updated_by_account_id=str(latest.account_id.value)
        if latest is not None
        else None,
        updated_at=latest.recorded_at.value.isoformat() if latest is not None else None,
        history=history,
    )
