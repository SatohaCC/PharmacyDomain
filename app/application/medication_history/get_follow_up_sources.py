"""独立フォローアップ薬歴の参照元候補を取得する処理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.access_control.policy import AuthorizationService
from app.application.access_control.store_access import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.medication_history.reference import (
    MedicationHistoryFollowUpSource,
    MedicationHistoryFollowUpSourceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class GetFollowUpSourcesQuery:
    """候補を必要とする患者と実施店舗。"""

    corporate_id: str
    patient_id: str
    store_id: str


@dataclass(frozen=True, kw_only=True)
class FollowUpSourceDto:
    """候補選択に必要な本文を含まない薬歴メタデータ。"""

    record_id: str
    record_kind: str
    source_record_id: str | None
    store_id: str
    dispensing_id: str
    prescription_id: str
    counseled_at: str


class GetFollowUpSourcesUseCase:
    """指定患者の確定済みフォローアップ参照候補を返す。"""

    def __init__(
        self,
        source_boundary: MedicationHistoryFollowUpSourceBoundary,
        corporate_access: CorporateAccessBoundary,
        store_operations: StoreOperationBoundary,
    ) -> None:
        self._source_boundary = source_boundary
        self._corporate_access = corporate_access
        self._store_operations = store_operations

    async def execute(
        self, query: GetFollowUpSourcesQuery
    ) -> tuple[FollowUpSourceDto, ...]:
        """店舗の新規業務権限を確認して、同一患者の確定済候補を返す。"""
        corporate_id, patient_id, store_id = _ids(
            query.corporate_id, query.patient_id, query.store_id
        )
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        AuthorizationService(self._corporate_access.actor).require_store(
            permission=Permission.MANAGE_MEDICATION_HISTORY,
            target_corporate_id=corporate_id,
            target_store_id=store_id,
        )
        await self._store_operations.require_allowed(
            corporate_id=corporate_id,
            store_id=store_id,
            operation=StoreOperation.START_HISTORY,
        )
        sources = await self._source_boundary.list_confirmed_sources(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        confirmed: list[tuple[MedicationHistoryFollowUpSource, datetime]] = []
        for source in sources:
            if source.status.value == "finalized" and source.counseled_at is not None:
                confirmed.append((source, source.counseled_at))
        confirmed.sort(
            key=lambda item: (item[1], item[0].record_id.value),
            reverse=True,
        )
        return tuple(_dto(source, counseled_at) for source, counseled_at in confirmed)


def _dto(
    source: MedicationHistoryFollowUpSource, counseled_at: datetime
) -> FollowUpSourceDto:
    """確定済み薬歴と日時を候補DTOへ写す。"""
    return FollowUpSourceDto(
        record_id=str(source.record_id.value),
        record_kind=source.record_kind.value,
        source_record_id=(
            str(source.source_record_id.value)
            if source.source_record_id is not None
            else None
        ),
        store_id=str(source.store_id.value),
        dispensing_id=str(source.dispensing_id.value),
        prescription_id=str(source.prescription_id.value),
        counseled_at=counseled_at.isoformat(),
    )


def _ids(
    corporate_id: str, patient_id: str, store_id: str
) -> tuple[CorporateId, PatientId, StoreId]:
    """候補検索のID入力を型付きIDへ変換する。"""
    return (
        CorporateId.parse(corporate_id),
        PatientId.parse(patient_id),
        StoreId.parse(store_id),
    )
