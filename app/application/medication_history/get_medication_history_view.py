"""薬歴本文と読取時点の患者プロフィールをまとめて返す契約。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import Permission
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryPatientProfileDto:
    """薬歴表示時に参照する患者の現行プロフィール。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: str | None
    gender: str | None
    postal_code: str | None
    address: str | None
    phone_number: str | None


class CurrentPatientProfileBoundary(Protocol):
    """Patient集約から読取時点のプロフィールを取得する境界。"""

    async def get_current_profile(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> MedicationHistoryPatientProfileDto | None:
        """法人・患者IDでプロフィールを取得する。"""
        ...


@dataclass(frozen=True, kw_only=True)
class GetMedicationHistoryViewQuery:
    """薬歴と現行患者プロフィールの表示用読取条件。"""

    corporate_id: str
    record_id: str


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryViewDto:
    """確定薬歴と読取時点の患者プロフィール。"""

    record: MedicationHistoryDto
    current_patient_profile: MedicationHistoryPatientProfileDto


class GetMedicationHistoryViewUseCase:
    """薬歴と現行患者プロフィールを一緒に読む契約。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        patient_profile: CurrentPatientProfileBoundary,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._patient_profile = patient_profile
        self._corporate_access = corporate_access

    async def execute(
        self,
        query: GetMedicationHistoryViewQuery,
    ) -> MedicationHistoryViewDto:
        """薬歴本文と患者現行情報を認可後に返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_PATIENT,
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        profile = await self._patient_profile.get_current_profile(
            corporate_id=corporate_id,
            patient_id=record.patient_id,
        )
        if profile is None:
            raise TenantBoundaryNotFoundError()
        return MedicationHistoryViewDto(
            record=MedicationHistoryDto.from_entity(record),
            current_patient_profile=profile,
        )
