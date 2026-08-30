"""受付で選択した適用資格を記録するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common.clock import Clock
from app.application.reception.get_coverage_selection import CoverageSelectionRecordDto
from app.application.reception.reference import (
    CoverageSelectionBoundary,
    PatientReferenceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.reception import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelectionRecord,
    CoverageSelectionRecordRepository,
    OperatorPrincipalId,
)
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class RecordCoverageSelectionCommand:
    """適用資格選択履歴登録の入力データ。監査値は含めない。"""

    corporate_id: str
    store_id: str
    patient_id: str
    applied_on: date
    coverage_ids: tuple[str, ...]


class RecordCoverageSelectionUseCase:
    """選択資格を信頼済み監査値とともに保存する。"""

    def __init__(
        self,
        repository: CoverageSelectionRecordRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        patient_reference: PatientReferenceBoundary,
        coverage_selection: CoverageSelectionBoundary,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._patient_reference = patient_reference
        self._coverage_selection = coverage_selection
        self._clock = clock

    async def execute(
        self,
        command: RecordCoverageSelectionCommand,
    ) -> CoverageSelectionRecordDto:
        """境界を確認し、認可ActorとClockから監査値を生成して保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_RECEPTION,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        patient_id = PatientId.parse(command.patient_id)
        await self._patient_reference.require_exists(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        applied_on = CoverageAppliedOn(command.applied_on)
        selection = await self._coverage_selection.build_selection(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_ids=command.coverage_ids,
            applied_on=applied_on,
        )
        record = CoverageSelectionRecord.create(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            applied_on=applied_on,
            selection=selection,
            recorded_at=CoverageRecordedAt(self._clock.now()),
            recorded_by=OperatorPrincipalId(self._corporate_access.actor.principal_id),
        )
        await self._repository.save(record)
        return CoverageSelectionRecordDto.from_entity(record)
