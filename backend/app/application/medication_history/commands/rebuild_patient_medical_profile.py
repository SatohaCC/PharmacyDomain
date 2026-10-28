"""Applicationのrebuild_patient_medical_profileを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.commands.dtos.get_patient_medical_profile import (
    PatientMedicalProfileDto,
)
from app.application.medication_history.commands.services.profile_projection_service import (
    PatientMedicalProfileProjectionService,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.repositories import (
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.patient.identifiers import PatientId


@dataclass(frozen=True, kw_only=True)
class RebuildPatientMedicalProfileCommand:
    """頭書き再構築の入力データ。"""

    corporate_id: str
    patient_id: str
    as_of: date


class RebuildPatientMedicalProfileUseCase:
    """確定済薬歴から頭書きを作り直す。

    患者単位のロックを取得したうえで全確定記録を時系列に再計算し、
    頭書きへ投影する。確定や訂正のトランザクションでは薬歴と頭書きが
    原子的に保存されるが、外部取り込みやデータ修復、差分再同期などの
    契機で全記録から決定論的に頭書きを再構築する際に利用する。

    既存の頭書きがあれば、その同一性（``id``）を保ったまま中身を差し替える。
    新しい ``id`` で作り直すと、患者ごと1件の一意制約に引っかかる。
    """

    def __init__(
        self,
        record_repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        *,
        organization_lock: OrganizationLock,
        projection_service: PatientMedicalProfileProjectionService | None = None,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._organization_lock = organization_lock
        self._projection_service = (
            projection_service
            or PatientMedicalProfileProjectionService(
                record_repository=record_repository,
                profile_repository=profile_repository,
            )
        )

    async def execute(
        self, command: RebuildPatientMedicalProfileCommand
    ) -> PatientMedicalProfileDto:
        """薬歴を畳み込んで頭書きを保存し直す。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_PATIENT
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._organization_lock.acquire(
            f"medication-history-retention:{corporate_id.value}:{patient_id.value}"
        )
        rebuilt = await self._projection_service.project(
            corporate_id=corporate_id, patient_id=patient_id
        )
        return PatientMedicalProfileDto.from_entity(rebuilt, as_of=command.as_of)
