"""外部訂正レビュー履歴のJSONB codec契約を検証する。"""

from dataclasses import replace
from datetime import UTC, datetime

from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    FinalizedTimestamp,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionDecision,
    ExternalCorrectionKind,
    ExternalCorrectionReviewEvent,
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
)
from app.domain.prescription.primitives import PrescriptionId
from app.domain.staff.primitives import StaffId
from app.infrastructure.postgres.codec import decode_aggregate, encode_aggregate
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_record,
    finalize_record_with_review,
)

_RECEIVED_AT = ExternalCorrectionTimestamp(datetime(2026, 8, 24, 7, 0, tzinfo=UTC))
_REVIEWED_AT = ExternalCorrectionTimestamp(datetime(2026, 8, 24, 7, 30, tzinfo=UTC))


def _finalized_record() -> MedicationHistoryRecord:
    draft = create_record(counseled_at=COUNSELED_AT)
    return finalize_record_with_review(
        draft,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=draft.counselor_id,
    )


def test_TC24_レビュー済み削除訂正の全履歴をcodecで往復する() -> None:
    reviewer = StaffId.generate()
    matched_id = PrescriptionId.generate()
    correction = ExternalPrescriptionCorrection(
        correction_id="corr-codec-001",
        corrected_at=_RECEIVED_AT,
        source_document_number="RX-CODEC-001",
        reason="NSIPS削除通知",
        kind=ExternalCorrectionKind.DELETE,
        status=ExternalCorrectionStatus.RESOLVED,
        review_events=(
            ExternalCorrectionReviewEvent(
                decision=ExternalCorrectionDecision.INVESTIGATING,
                reason="再登録の有無を確認中。",
                reviewed_by=reviewer,
                reviewed_at=_REVIEWED_AT,
            ),
            ExternalCorrectionReviewEvent(
                decision=ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION,
                reason="再登録処方との一致を確認した。",
                reviewed_by=reviewer,
                reviewed_at=_REVIEWED_AT,
                matched_prescription_id=matched_id,
            ),
        ),
    )
    record = replace(_finalized_record(), external_corrections=(correction,))

    payload = encode_aggregate(record)
    restored = decode_aggregate(payload, MedicationHistoryRecord)

    assert encode_aggregate(restored) == payload
    assert restored.external_corrections == (correction,)
    assert restored.external_corrections[0].review_events[
        1
    ].matched_prescription_id == (matched_id)


def test_TC25_旧訂正payloadの未確認と確認済み状態を保つ() -> None:
    reviewer = StaffId.generate()
    pending = ExternalPrescriptionCorrection(
        correction_id="corr-legacy-pending",
        corrected_at=_RECEIVED_AT,
        source_document_number="RX-LEGACY-001",
        reason="旧形式の外部訂正",
    )
    acknowledged = replace(
        pending,
        correction_id="corr-legacy-acknowledged",
        acknowledged_at=_REVIEWED_AT,
        acknowledged_by=reviewer,
    )
    record = replace(_finalized_record(), external_corrections=(pending, acknowledged))
    legacy_payload = encode_aggregate(record)
    legacy_items = legacy_payload["external_corrections"]
    assert isinstance(legacy_items, list)
    for item in legacy_items:
        assert isinstance(item, dict)
        item.pop("kind")
        item.pop("status")
        item.pop("review_events")

    restored = decode_aggregate(legacy_payload, MedicationHistoryRecord)

    assert restored.external_corrections[0].is_acknowledged is False
    assert restored.external_corrections[1].is_acknowledged is True
    assert restored.has_pending_correction_review is True


def test_TC25_旧payloadで訂正履歴が欠落していれば空で復元する() -> None:
    payload = encode_aggregate(_finalized_record())
    payload.pop("external_corrections")

    restored = decode_aggregate(payload, MedicationHistoryRecord)

    assert restored.external_corrections == ()
    assert restored.has_pending_correction_review is False
