"""患者詳細取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.patient.support import load_patient_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository


@dataclass(frozen=True, kw_only=True)
class GetPatientQuery:
    """患者詳細取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str


@dataclass(frozen=True, kw_only=True)
class PatientStatusChangeDto:
    """患者状態変更履歴DTO。"""

    before: str
    after: str
    reason: str
    person_id: str
    account_id: str
    recorded_at: str
    merged_into_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class PatientDto:
    """患者詳細の出力データ（DTO）。"""

    id: str
    patient_number: int
    corporate_id: str
    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str | None
    status: str = "active"
    merged_into_id: str | None = None
    status_history: tuple[PatientStatusChangeDto, ...] = ()

    @classmethod
    def from_entity(cls, patient: Patient) -> PatientDto:
        """Patient集約から患者情報DTOを生成する。"""
        return cls(
            id=str(patient.id.value),
            patient_number=patient.patient_number.value,
            corporate_id=str(patient.corporate_id.value),
            last_name=patient.names.kanji.last_name.value,
            first_name=patient.names.kanji.first_name.value,
            last_name_kana=patient.names.kana.last_name.value,
            first_name_kana=patient.names.kana.first_name.value,
            birth_date=(
                patient.birth_date.value.isoformat() if patient.birth_date else None
            ),
            status=patient.status.value,
            merged_into_id=str(patient.merged_into_id.value)
            if patient.merged_into_id
            else None,
            status_history=tuple(
                PatientStatusChangeDto(
                    before=change.before.value,
                    after=change.after.value,
                    reason=change.reason.value,
                    person_id=str(change.person_id.value),
                    account_id=str(change.account_id.value),
                    recorded_at=change.recorded_at.isoformat(),
                    merged_into_id=str(change.merged_into_id.value)
                    if change.merged_into_id
                    else None,
                )
                for change in patient.status_history
            ),
        )


class GetPatientUseCase:
    """患者詳細を取得するアプリケーションサービス。"""

    def __init__(
        self,
        repository: PatientRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, query: GetPatientQuery) -> PatientDto:
        """法人境界を確認して患者情報DTOを返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT,
        )
        patient_id = PatientId.parse(query.patient_id)
        patient = await load_patient_or_raise(
            self._repository,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        return PatientDto.from_entity(patient)
