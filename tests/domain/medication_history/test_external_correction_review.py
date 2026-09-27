"""外部処方訂正の判断履歴と解決状態を検証する。"""

from datetime import UTC, datetime

import pytest

from app.domain.medication_history.exceptions import MedicationHistoryDomainError
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
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
    SoapRecord,
)
from app.domain.prescription.primitives import PrescriptionId
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_record,
    create_soap,
    finalize_record_with_review,
)

_RECEIVED_AT = ExternalCorrectionTimestamp(datetime(2026, 8, 24, 7, 0, tzinfo=UTC))
_REVIEWED_AT = ExternalCorrectionTimestamp(datetime(2026, 8, 24, 7, 30, tzinfo=UTC))


def _correction(
    *, kind: ExternalCorrectionKind = ExternalCorrectionKind.UPDATE
) -> ExternalPrescriptionCorrection:
    """外部訂正証跡を組み立てる。"""
    return ExternalPrescriptionCorrection(
        correction_id="corr-review-001",
        corrected_at=_RECEIVED_AT,
        source_document_number="RX-20260824-001",
        reason="NSIPS外部処方訂正",
        details="用法変更",
        kind=kind,
    )


def _record() -> MedicationHistoryRecord:
    """外部訂正の確認対象となる確定済み薬歴を作る。"""
    record = create_record(
        counseled_at=COUNSELED_AT,
        soap=create_soap(subjective="原本の指導記録。"),
    )
    return finalize_record_with_review(
        record,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=record.counselor_id,
    ).record_external_correction(_correction())


def test_TC02_追記訂正とレビュー判断を同じ薬歴へ追記する() -> None:
    record = _record()
    reviewer = StaffId.generate()

    reviewed = record.review_external_correction(
        correction_id="corr-review-001",
        decision=ExternalCorrectionDecision.AMEND,
        reason="変更内容を患者へ説明し、指導内容を追記した。",
        reviewed_by=reviewer,
        reviewed_at=_REVIEWED_AT,
        amended_soap=create_soap(subjective="変更内容の説明を追記。"),
    )

    correction = reviewed.external_corrections[0]
    assert len(reviewed.amendments) == 1
    assert reviewed.soap == record.soap
    assert reviewed.finalized_at == record.finalized_at
    assert reviewed.finalized_by == record.finalized_by
    assert correction.status is ExternalCorrectionStatus.RESOLVED
    assert correction.review_events[-1].decision is ExternalCorrectionDecision.AMEND
    assert correction.review_events[-1].reviewed_by == reviewer
    assert correction.review_events[-1].reviewed_at == _REVIEWED_AT
    assert correction.review_events[-1].amendment_id is not None
    assert (
        reviewed.amendments[-1].amendment_id
        == correction.review_events[-1].amendment_id
    )
    assert reviewed.has_pending_correction_review is False


def test_TC03_理由付き不採用は解決し空白理由は拒否する() -> None:
    record = _record()
    reviewer = StaffId.generate()

    resolved = record.review_external_correction(
        correction_id="corr-review-001",
        decision=ExternalCorrectionDecision.NO_ACTION,
        reason="指導内容と安全性に影響しない訂正であることを確認した。",
        reviewed_by=reviewer,
        reviewed_at=_REVIEWED_AT,
    )

    assert resolved.external_corrections[0].status is ExternalCorrectionStatus.RESOLVED
    assert resolved.external_corrections[0].review_events[-1].reason
    assert resolved.amendments == record.amendments
    assert resolved.has_pending_correction_review is False

    with pytest.raises(MedicationHistoryDomainError):
        record.review_external_correction(
            correction_id="corr-review-001",
            decision=ExternalCorrectionDecision.NO_ACTION,
            reason="  ",
            reviewed_by=reviewer,
            reviewed_at=_REVIEWED_AT,
        )


def test_TC04_調査中の履歴を残してから最終判断へ進める() -> None:
    record = _record()
    reviewer = StaffId.generate()
    investigating = record.review_external_correction(
        correction_id="corr-review-001",
        decision=ExternalCorrectionDecision.INVESTIGATING,
        reason="処方元へ変更の意図を照会中。",
        reviewed_by=reviewer,
        reviewed_at=_REVIEWED_AT,
    )

    assert investigating.external_corrections[0].status is (
        ExternalCorrectionStatus.INVESTIGATING
    )
    assert investigating.has_pending_correction_review is True
    resolved = investigating.review_external_correction(
        correction_id="corr-review-001",
        decision=ExternalCorrectionDecision.NO_ACTION,
        reason="処方元の回答を確認し、変更は不要と判断した。",
        reviewed_by=reviewer,
        reviewed_at=ExternalCorrectionTimestamp(
            datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
        ),
    )
    assert len(resolved.external_corrections[0].review_events) == 2
    assert resolved.external_corrections[0].review_events[0].decision is (
        ExternalCorrectionDecision.INVESTIGATING
    )
    assert resolved.external_corrections[0].status is ExternalCorrectionStatus.RESOLVED


def test_TC05_削除訂正を再登録処方IDと照合する() -> None:
    draft = create_record(counseled_at=COUNSELED_AT)
    original = finalize_record_with_review(
        draft,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=draft.counselor_id,
    )
    correction = _correction(kind=ExternalCorrectionKind.DELETE)
    record = original.record_external_correction(correction)
    reviewer = StaffId.generate()
    matched_id = PrescriptionId.generate()

    resolved = record.review_external_correction(
        correction_id=correction.correction_id,
        decision=ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION,
        reason="再登録された同一処方箋であることを確認した。",
        reviewed_by=reviewer,
        reviewed_at=_REVIEWED_AT,
        matched_prescription_id=matched_id,
    )

    assert resolved.external_corrections[0].status is ExternalCorrectionStatus.RESOLVED
    assert resolved.external_corrections[0].review_events[
        -1
    ].matched_prescription_id == (matched_id)


@pytest.mark.parametrize(
    ("decision", "reason", "amended_soap", "matched_prescription_id"),
    [
        (ExternalCorrectionDecision.AMEND, "追記する", None, None),
        (
            ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION,
            "照合",
            None,
            None,
        ),
    ],
)
def test_TC06_判断に必要な追記や照合先の欠落を拒否する(
    decision: ExternalCorrectionDecision,
    reason: str,
    amended_soap: SoapRecord | None,
    matched_prescription_id: PrescriptionId | None,
) -> None:
    record = _record()
    before = record.external_corrections

    with pytest.raises(MedicationHistoryDomainError):
        record.review_external_correction(
            correction_id="corr-review-001",
            decision=decision,
            reason=reason,
            reviewed_by=StaffId.generate(),
            reviewed_at=_REVIEWED_AT,
            amended_soap=amended_soap,
            matched_prescription_id=matched_prescription_id,
        )

    assert record.external_corrections == before


def test_TC07_存在しない外部訂正IDは変更できない() -> None:
    record = _record()

    with pytest.raises(MedicationHistoryDomainError):
        record.review_external_correction(
            correction_id="unknown-correction",
            decision=ExternalCorrectionDecision.NO_ACTION,
            reason="確認した。",
            reviewed_by=StaffId.generate(),
            reviewed_at=_REVIEWED_AT,
        )


def test_TC08_同じ外部訂正IDの再記録は重複しない() -> None:
    record = _record()
    duplicate = record.record_external_correction(_correction())

    assert len(duplicate.external_corrections) == 1
    assert duplicate.external_corrections[0] == record.external_corrections[0]


def test_TC09_解決済み訂正への再判断は元履歴を上書きしない() -> None:
    record = _record()
    reviewer = StaffId.generate()
    resolved = record.review_external_correction(
        correction_id="corr-review-001",
        decision=ExternalCorrectionDecision.NO_ACTION,
        reason="影響なし。",
        reviewed_by=reviewer,
        reviewed_at=_REVIEWED_AT,
    )
    old_events = resolved.external_corrections[0].review_events

    with pytest.raises(MedicationHistoryDomainError):
        resolved.review_external_correction(
            correction_id="corr-review-001",
            decision=ExternalCorrectionDecision.AMEND,
            reason="後から追記する。",
            reviewed_by=reviewer,
            reviewed_at=_REVIEWED_AT,
            amended_soap=create_soap(subjective="追記。"),
        )

    assert resolved.external_corrections[0].review_events == old_events
