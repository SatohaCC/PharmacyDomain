"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.common.optional_conversion import unwrap
from app.application.common.pagination import MAX_PAGE_SIZE, Page
from app.application.medication_history.interfaces.list_pending_external_corrections_query_reader import (
    ListPendingExternalCorrectionsQueryReader,
)
from app.application.medication_history.queries.dtos.list_pending_external_corrections import (
    PendingExternalCorrectionDto,
)
from app.application.medication_history.queries.models import (
    ListPendingExternalCorrectionsQuery,
)
from app.application.medication_history.queries.services.list_pending_external_corrections import (
    _decode_cursor,
    _encode_cursor,
)
from app.application.medication_history.values import parse_enum
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.primitives import ExternalCorrectionStatus
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.store.identifiers import StoreId


class ListPendingExternalCorrectionsProjection(
    ListPendingExternalCorrectionsQueryReader
):
    """権限範囲内の外部訂正をページングして返す。"""

    def __init__(self, repository: MedicationHistoryRepository) -> None:
        self.repository = repository
        self._repository = repository

    async def read(
        self, query: ListPendingExternalCorrectionsQuery
    ) -> Page[PendingExternalCorrectionDto]:
        """状態、法人、店舗をRepository検索へ渡し、安定cursorで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        if query.limit < 1 or query.limit > MAX_PAGE_SIZE:
            raise ValueError(
                f"一覧件数は1から{MAX_PAGE_SIZE}の範囲で指定してください。"
            )
        store_id = StoreId.parse(query.store_id) if query.store_id is not None else None
        status = (
            parse_enum(ExternalCorrectionStatus, query.status, "訂正状態")
            if query.status is not None
            else None
        )
        statuses = (
            (status,)
            if status is not None
            else (
                ExternalCorrectionStatus.PENDING,
                ExternalCorrectionStatus.INVESTIGATING,
            )
        )
        after = _decode_cursor(query.cursor) if query.cursor is not None else None
        candidates = await self._repository.list_external_corrections(
            corporate_id=corporate_id,
            store_id=store_id,
            statuses=statuses,
            after=after,
            limit=query.limit + 1,
        )
        has_next = len(candidates) > query.limit
        page_candidates = candidates[: query.limit]
        next_cursor = (
            _encode_cursor(
                str(page_candidates[-1].record.id.value),
                page_candidates[-1].correction.correction_id.value,
            )
            if has_next and page_candidates
            else None
        )
        items = tuple(
            PendingExternalCorrectionDto(
                record_id=str(match.record.id.value),
                corporate_id=str(match.record.corporate_id.value),
                store_id=str(match.record.store_id.value),
                patient_id=str(match.record.patient_id.value),
                correction_id=match.correction.correction_id.value,
                correction_kind=match.correction.kind.value,
                correction_status=ExternalCorrectionStatus.RESOLVED.value
                if match.correction.is_acknowledged
                else match.correction.status.value,
                source_document_number=match.correction.source_document_number.value,
                reason=match.correction.reason.value,
                details=unwrap(match.correction.details),
                corrected_at=match.correction.corrected_at.value.isoformat(),
                review_events=tuple(
                    {
                        "decision": event.decision.value,
                        "reason": event.reason.value,
                        "reviewed_by": str(event.reviewed_by.value),
                        "reviewed_at": event.reviewed_at.value.isoformat(),
                        "matched_prescription_id": str(
                            event.matched_prescription_id.value
                        )
                        if event.matched_prescription_id is not None
                        else None,
                    }
                    for event in match.correction.review_events
                ),
            )
            for match in page_candidates
        )
        return Page(items=items, next_cursor=next_cursor)
