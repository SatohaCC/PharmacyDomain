"""患者詳細取得ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.optional_conversion import unwrap
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
class PatientProfileSnapshotDto:
    """受信したプロフィール値DTO。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str
    gender: str | None
    postal_code: str | None
    address: str | None
    phone_number: str | None


@dataclass(frozen=True, kw_only=True)
class PatientProfileChangeDto:
    """患者プロフィール変更履歴DTO。"""

    reception_id: str
    store_id: str
    external_patient_id: str
    recorded_at: str
    changed_fields: tuple[str, ...]
    received_profile: PatientProfileSnapshotDto


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
    gender: str | None = None
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None
    status: str = "active"
    merged_into_id: str | None = None
    status_history: tuple[PatientStatusChangeDto, ...] = ()
    profile_history: tuple[PatientProfileChangeDto, ...] = ()

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
            gender=unwrap(patient.gender),
            postal_code=unwrap(patient.postal_code),
            address=unwrap(patient.address),
            phone_number=unwrap(patient.phone_number),
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
            profile_history=tuple(
                PatientProfileChangeDto(
                    reception_id=str(change.reception_id.value),
                    store_id=str(change.store_id.value),
                    external_patient_id=change.external_patient_id.value,
                    recorded_at=change.recorded_at.isoformat(),
                    changed_fields=change.changed_fields,
                    received_profile=PatientProfileSnapshotDto(
                        last_name=change.received_profile.names.kanji.last_name.value,
                        first_name=change.received_profile.names.kanji.first_name.value,
                        last_name_kana=change.received_profile.names.kana.last_name.value,
                        first_name_kana=change.received_profile.names.kana.first_name.value,
                        birth_date=change.received_profile.birth_date.value.isoformat(),
                        gender=unwrap(change.received_profile.gender),
                        postal_code=unwrap(change.received_profile.postal_code),
                        address=unwrap(change.received_profile.address),
                        phone_number=unwrap(change.received_profile.phone_number),
                    ),
                )
                for change in patient.profile_history
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
