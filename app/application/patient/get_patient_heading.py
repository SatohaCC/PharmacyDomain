"""患者頭書きの参照契約。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import unwrap
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.heading import PatientHeadingRevision
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class GetPatientHeadingQuery:
    """患者頭書き参照の入力。"""

    corporate_id: str
    patient_id: str


@dataclass(frozen=True, kw_only=True)
class PatientHeadingRevisionDto:
    """患者頭書き1改訂分の応答。"""

    revision: int
    summary: str | None
    notes: str | None
    person_id: str
    account_id: str
    recorded_at: str


@dataclass(frozen=True, kw_only=True)
class PatientHeadingDto:
    """患者頭書きの現在値と変更履歴の応答。"""

    patient_id: str
    revision: int
    summary: str | None
    notes: str | None
    updated_by_person_id: str | None
    updated_by_account_id: str | None
    updated_at: str | None
    history: tuple[PatientHeadingRevisionDto, ...]


class GetPatientHeadingUseCase:
    """患者頭書きを参照するユースケース契約。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientHeadingQuery) -> PatientHeadingDto:
        """認可と法人境界を確かめて頭書きを取得する。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT_HEADING,
        )
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=PatientId.parse(query.patient_id),
        )
        return _to_dto(str(patient.id.value), patient.heading_history)


def _to_dto(
    patient_id: str, revisions: tuple[PatientHeadingRevision, ...]
) -> PatientHeadingDto:
    """履歴から頭書きの現在値と改訂一覧を組み立てる。"""
    history = tuple(
        PatientHeadingRevisionDto(
            revision=index,
            summary=unwrap(revision.content.summary),
            notes=unwrap(revision.content.notes),
            person_id=str(revision.person_id.value),
            account_id=str(revision.account_id.value),
            recorded_at=revision.recorded_at.isoformat(),
        )
        for index, revision in enumerate(revisions, start=1)
    )
    latest = revisions[-1] if revisions else None
    return PatientHeadingDto(
        patient_id=patient_id,
        revision=len(revisions),
        summary=unwrap(latest.content.summary) if latest is not None else None,
        notes=unwrap(latest.content.notes) if latest is not None else None,
        updated_by_person_id=(
            str(latest.person_id.value) if latest is not None else None
        ),
        updated_by_account_id=(
            str(latest.account_id.value) if latest is not None else None
        ),
        updated_at=latest.recorded_at.isoformat() if latest is not None else None,
        history=history,
    )
