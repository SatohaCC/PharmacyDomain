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
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
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
    """患者プロフィールのある時点の値DTO。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str | None
    gender: str | None
    postal_code: str | None
    address: str | None
    phone_number: str | None

    @classmethod
    def from_entity(
        cls,
        profile: PatientProfileSnapshot,
    ) -> PatientProfileSnapshotDto:
        """プロフィール履歴SnapshotをDTOへ変換する。"""
        return cls(
            last_name=profile.names.kanji.last_name.value,
            first_name=profile.names.kanji.first_name.value,
            last_name_kana=profile.names.kana.last_name.value,
            first_name_kana=profile.names.kana.first_name.value,
            birth_date=(
                profile.birth_date.value.isoformat()
                if profile.birth_date is not None
                else None
            ),
            gender=unwrap(profile.gender),
            postal_code=unwrap(profile.postal_code),
            address=unwrap(profile.address),
            phone_number=unwrap(profile.phone_number),
        )


@dataclass(frozen=True, kw_only=True)
class PatientProfileChangeDto:
    """患者プロフィール変更履歴DTO。"""

    recorded_at: str
    changed_fields: tuple[str, ...]
    source: str = "nsips"
    reception_id: str | None = None
    store_id: str | None = None
    external_patient_id: str | None = None
    received_profile: PatientProfileSnapshotDto | None = None
    before_profile: PatientProfileSnapshotDto | None = None
    applied_profile: PatientProfileSnapshotDto | None = None
    person_id: str | None = None
    account_id: str | None = None

    @classmethod
    def from_entity(cls, change: PatientProfileChange) -> PatientProfileChangeDto:
        """プロフィール変更履歴をDTOへ変換する。"""
        return cls(
            recorded_at=change.recorded_at.isoformat(),
            changed_fields=change.changed_fields,
            source=change.source.value,
            reception_id=(
                str(change.reception_id.value)
                if change.reception_id is not None
                else None
            ),
            store_id=str(change.store_id.value)
            if change.store_id is not None
            else None,
            external_patient_id=unwrap(change.external_patient_id),
            received_profile=(
                PatientProfileSnapshotDto.from_entity(change.received_profile)
                if change.received_profile is not None
                else None
            ),
            before_profile=(
                PatientProfileSnapshotDto.from_entity(change.before_profile)
                if change.before_profile is not None
                else None
            ),
            applied_profile=(
                PatientProfileSnapshotDto.from_entity(change.applied_profile)
                if change.applied_profile is not None
                else None
            ),
            person_id=str(change.person_id.value)
            if change.person_id is not None
            else None,
            account_id=str(change.account_id.value)
            if change.account_id is not None
            else None,
        )


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
                PatientProfileChangeDto.from_entity(change)
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
