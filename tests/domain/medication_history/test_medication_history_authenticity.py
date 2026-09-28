"""薬歴集約の法定保存満了日および真正性保護（改竄防止・外部処方訂正追跡）のテスト。"""

from datetime import UTC, date, datetime

from app.domain.medication_history.primitives import (
    AmendmentReason,
    AmendmentTimestamp,
    ExternalCorrectionTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionKind,
    ExternalCorrectionStatus,
    ExternalPrescriptionCorrection,
)
from app.domain.shared.preservation import (
    PreservationPolicyCatalog,
    PreservationRecordKind,
)
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_record,
    create_soap,
    finalize_record_with_review,
)


def test_finalize_records_retention_expiry() -> None:
    """TC-13: 明示した最終記入日から薬歴の保存満了日が計算される。"""
    record = create_record(counseled_at=COUNSELED_AT)
    catalog = PreservationPolicyCatalog.create_standard_statutory_catalog(
        PreservationRecordKind.MEDICATION_HISTORY
    )
    finalized_on = date(2026, 8, 25)

    # 指導日は8月24日、確定・最終記入日は8月25日としてカタログを適用
    finalized = finalize_record_with_review(
        record,
        finalized_at=FinalizedTimestamp(datetime(2026, 8, 25, 5, tzinfo=UTC)),
        finalized_by=record.counselor_id,
        delay_reason=FinalizationDelayReason("薬剤師の確認を経て翌日に確定した。"),
    ).calculate_and_set_retention_expiry(catalog, last_written_on=finalized_on)

    # 薬剤服用歴は法改正後も最終記入日から3年間保存する。
    assert finalized.retention_expiry_date == date(2029, 8, 25)


def test_record_external_correction_preserves_original() -> None:
    """TC-14: 確定済み薬歴に外部訂正を記録しても原本（SOAP・確定メタデータ）は不可逆凍結される。"""
    record = create_record(
        counseled_at=COUNSELED_AT,
        soap=create_soap(subjective="指導時: 処方日数7日分を確認"),
    )
    finalized = finalize_record_with_review(
        record,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=record.counselor_id,
    )

    correction = ExternalPrescriptionCorrection(
        correction_id="corr-001",
        corrected_at=ExternalCorrectionTimestamp(
            datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
        ),
        source_document_number="RX-20260824-001",
        reason="レセコンUファイル受信: 疑義照会に伴う日数短縮（7日->5日）",
        details="Rp1 ロキソプロフェン 7日分 -> 5日分に変更",
    )

    # 外部訂正を記録
    updated = finalized.record_external_correction(correction)

    # 1. 原本記録が1文字も変化していないこと（真正性保証）
    assert updated.soap == finalized.soap
    assert updated.effective_soap == finalized.effective_soap
    assert updated.counseled_at == finalized.counseled_at
    assert updated.finalized_at == finalized.finalized_at
    assert updated.finalized_by == finalized.finalized_by
    assert updated.status == finalized.status

    # 2. 外部訂正が追記され、未確認フラグが立っていること
    assert len(updated.external_corrections) == 1
    assert updated.external_corrections[0].correction_id == "corr-001"
    assert updated.external_corrections[0].kind is ExternalCorrectionKind.UPDATE
    assert updated.external_corrections[0].status is ExternalCorrectionStatus.PENDING
    assert updated.has_pending_correction_review is True


def test_acknowledge_external_correction() -> None:
    """TC-15: 薬剤師による外部処方訂正の確認により要確認フラグが解消される。"""
    record = finalize_record_with_review(create_record(counseled_at=COUNSELED_AT))
    correction = ExternalPrescriptionCorrection(
        correction_id="corr-001",
        corrected_at=ExternalCorrectionTimestamp(
            datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
        ),
        source_document_number="RX-20260824-001",
        reason="レセコンUファイル受信: 用法変更",
    )
    updated = record.record_external_correction(correction)
    assert updated.has_pending_correction_review is True

    reviewer = StaffId.generate()
    reviewed_at = ExternalCorrectionTimestamp(datetime(2026, 8, 24, 7, 30, tzinfo=UTC))

    # 確認を記録
    acknowledged = updated.acknowledge_external_correction(
        correction_id="corr-001",
        acknowledged_by=reviewer,
        acknowledged_at=reviewed_at,
    )

    assert acknowledged.has_pending_correction_review is False
    assert acknowledged.external_corrections[0].is_acknowledged is True
    assert acknowledged.external_corrections[0].acknowledged_by == reviewer


def test_amend_after_external_correction() -> None:
    """TC-16: 外部訂正を受けた後に薬剤師が指導追補（amend）を行った場合、新旧記録が保全される。"""
    record = finalize_record_with_review(create_record(counseled_at=COUNSELED_AT))
    correction = ExternalPrescriptionCorrection(
        correction_id="corr-001",
        corrected_at=ExternalCorrectionTimestamp(
            datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
        ),
        source_document_number="RX-20260824-001",
        reason="日数変更",
    )
    with_corr = record.record_external_correction(correction)

    # 薬剤師が処方変更に伴う指導追補を記載
    assert record.counselor_id is not None
    amended = with_corr.amend(
        amended_soap=create_soap(
            subjective="処方日数短縮（5日分）について患者へ再説明完了。"
        ),
        reason=AmendmentReason("レセコンUファイル処方変更に伴う服薬指導追補"),
        amended_by=record.counselor_id,
        amended_at=AmendmentTimestamp(datetime(2026, 8, 24, 7, 45, tzinfo=UTC)),
    )

    # 元のSOAPと追記後のSOAPが両立して保持される
    assert amended.soap == record.soap
    assert amended.effective_soap != record.soap
    assert len(amended.amendments) == 1
    assert len(amended.external_corrections) == 1
