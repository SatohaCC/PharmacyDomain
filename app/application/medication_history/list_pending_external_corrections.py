"""外部処方訂正の未完了一覧公開インターフェース。"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import ActorRole, Permission
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.common.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
)
from app.application.medication_history.support import parse_enum
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.value_objects import ExternalCorrectionStatus
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class ListPendingExternalCorrectionsQuery:
    """外部訂正の未完了一覧検索条件。"""

    corporate_id: str
    store_id: str | None = None
    cursor: str | None = None
    limit: int = DEFAULT_PAGE_SIZE
    status: str | None = None


@dataclass(frozen=True, kw_only=True)
class PendingExternalCorrectionDto:
    """未完了の外部訂正と薬歴参照情報。"""

    record_id: str
    corporate_id: str
    store_id: str
    patient_id: str
    correction_id: str
    correction_kind: str
    correction_status: str
    source_document_number: str
    reason: str
    details: str | None
    corrected_at: str
    review_events: tuple[dict[str, str | None], ...]


class ListPendingExternalCorrectionsUseCase:
    """権限範囲内の外部訂正をページングして返す。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self.repository = repository
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, query: ListPendingExternalCorrectionsQuery
    ) -> Page[PendingExternalCorrectionDto]:
        """状態、法人、店舗をRepository検索へ渡し、安定cursorで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        if query.limit < 1 or query.limit > MAX_PAGE_SIZE:
            raise ValueError(
                f"一覧件数は1から{MAX_PAGE_SIZE}の範囲で指定してください。"
            )
        access = AuthorizationService(self._corporate_access.actor)
        actor = access.actor
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        store_id = StoreId.parse(query.store_id) if query.store_id is not None else None
        if store_id is not None:
            access.require_store(
                permission=Permission.VIEW_MEDICATION_HISTORY,
                target_corporate_id=corporate_id,
                target_store_id=store_id,
            )
        elif not actor.roles & {
            ActorRole.VENDOR_SYSTEM_ADMIN,
            ActorRole.CORPORATE_ADMIN,
        }:
            raise AuthorizationError("店舗ロールでは店舗IDを指定してください。")

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
                page_candidates[-1].correction.correction_id,
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
                correction_id=match.correction.correction_id,
                correction_kind=match.correction.kind.value,
                correction_status=(
                    ExternalCorrectionStatus.RESOLVED.value
                    if match.correction.is_acknowledged
                    else match.correction.status.value
                ),
                source_document_number=match.correction.source_document_number,
                reason=match.correction.reason,
                details=match.correction.details,
                corrected_at=match.correction.corrected_at.value.isoformat(),
                review_events=tuple(
                    {
                        "decision": event.decision.value,
                        "reason": event.reason,
                        "reviewed_by": str(event.reviewed_by.value),
                        "reviewed_at": event.reviewed_at.value.isoformat(),
                        "matched_prescription_id": (
                            str(event.matched_prescription_id.value)
                            if event.matched_prescription_id is not None
                            else None
                        ),
                    }
                    for event in match.correction.review_events
                ),
            )
            for match in page_candidates
        )
        return Page(items=items, next_cursor=next_cursor)


def _encode_cursor(record_id: str, correction_id: str) -> str:
    """複合キーを不透明なURL-safe cursorへ変換する。"""
    value = json.dumps([record_id, correction_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    """cursorを検証し、複合キーへ戻す。"""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("一覧cursorが不正です。") from exc
    if (
        not isinstance(decoded, list)
        or len(decoded) != 2
        or not all(isinstance(item, str) for item in decoded)
    ):
        raise ValueError("一覧cursorが不正です。")
    return decoded[0], decoded[1]
