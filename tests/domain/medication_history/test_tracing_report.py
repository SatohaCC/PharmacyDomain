"""処方医への服薬情報等提供（トレーシングレポート）のドメインテスト。"""

from datetime import timedelta
from typing import Any

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import (
    DuplicatedTracingReportIdError,
    FollowUpNotFoundError,
    TracingReportAlreadyRespondedError,
    TracingReportDateBeforeCounselingError,
    TracingReportDateBeforeFollowUpError,
    TracingReportNotFoundError,
    TracingReportOnDraftError,
    TracingReportResponseDateBeforeProvidedError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    FollowUpId,
    PhysicianName,
    PrescriberActionType,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportResponseContent,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_follow_up,
    create_record,
    create_tracing_report,
    create_tracing_report_response,
    finalize_record_with_review,
)


def _finalized_record(**kwargs: Any) -> MedicationHistoryRecord:
    record = create_record(**kwargs)
    return finalize_record_with_review(record)


class TestTracingReportDomain:
    """トレーシングレポートおよび薬歴集約の不変条件テスト。"""

    def test_add_tracing_report_to_finalized_record(self) -> None:
        """TC-DOM-01: 確定済み薬歴に完全なトレーシングレポートを追加できる（不変性の維持）。"""
        record = _finalized_record()
        report = create_tracing_report(
            provided_at=COUNSELED_AT + timedelta(days=1),
            category=TracingReportCategory.RESIDUAL_DRUG,
            fee_category=TracingReportFeeCategory.FEE_2,
            delivery_method=TracingReportDeliveryMethod.FAX,
            content="残薬14日分の調整提案。",
        )

        updated = record.add_tracing_report(report)

        assert len(updated.tracing_reports) == 1
        assert updated.tracing_reports[0].id == report.id
        assert (
            updated.tracing_reports[0].category == TracingReportCategory.RESIDUAL_DRUG
        )
        assert updated.tracing_reports[0].fee_category == TracingReportFeeCategory.FEE_2
        assert (
            updated.tracing_reports[0].delivery_method
            == TracingReportDeliveryMethod.FAX
        )
        assert updated.tracing_reports[0].content.value == "残薬14日分の調整提案。"
        assert updated.tracing_reports[0].response is None
        assert not updated.tracing_reports[0].is_responded
        # 元インスタンスは不変
        assert len(record.tracing_reports) == 0

    def test_add_multiple_tracing_reports(self) -> None:
        """TC-DOM-02: 確定済み薬歴に複数のトレーシングレポートを追加できる。"""
        record = _finalized_record()
        rep1 = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))
        rep2 = create_tracing_report(
            provided_at=COUNSELED_AT + timedelta(days=5),
            category=TracingReportCategory.ADVERSE_REACTION,
        )

        updated = record.add_tracing_report(rep1).add_tracing_report(rep2)

        assert len(updated.tracing_reports) == 2
        assert updated.tracing_reports[0].id == rep1.id
        assert updated.tracing_reports[1].id == rep2.id

    def test_add_tracing_report_linked_to_follow_up(self) -> None:
        """TC-DOM-03: フォローアップに紐付けたトレーシングレポートを追加できる。"""
        follow_up_time = COUNSELED_AT + timedelta(days=3)
        fu = create_follow_up(followed_up_at=follow_up_time)
        record = _finalized_record().add_follow_up(fu)

        report = create_tracing_report(
            provided_at=follow_up_time + timedelta(hours=2),
            follow_up_id=fu.id,
            category=TracingReportCategory.ADVERSE_REACTION,
        )

        updated = record.add_tracing_report(report)
        assert len(updated.tracing_reports) == 1
        assert updated.tracing_reports[0].follow_up_id == fu.id

    def test_add_tracing_report_on_draft_raises_error(self) -> None:
        """TC-DOM-04: 下書き状態の薬歴への追加は拒否される。"""
        draft_record = create_record()  # 未確定
        report = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))

        with pytest.raises(TracingReportOnDraftError):
            draft_record.add_tracing_report(report)

    def test_add_tracing_report_before_counseling_raises_error(self) -> None:
        """TC-DOM-05: 初回服薬指導日時より前の提供日時は拒否される。"""
        record = _finalized_record()
        past_time = COUNSELED_AT - timedelta(hours=1)
        report = create_tracing_report(provided_at=past_time)

        with pytest.raises(TracingReportDateBeforeCounselingError):
            record.add_tracing_report(report)

    def test_add_tracing_report_with_unknown_follow_up_raises_error(self) -> None:
        """TC-DOM-06: 存在しないフォローアップ参照は拒否される。"""
        record = _finalized_record()
        unknown_fu_id = FollowUpId.generate()
        report = create_tracing_report(
            provided_at=COUNSELED_AT + timedelta(days=1),
            follow_up_id=unknown_fu_id,
        )

        with pytest.raises(FollowUpNotFoundError):
            record.add_tracing_report(report)

    def test_add_tracing_report_before_follow_up_date_raises_error(self) -> None:
        """TC-DOM-07: 紐付け先フォローアップ日時より前の提供日時は拒否される。"""
        fu = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=3))
        record = _finalized_record().add_follow_up(fu)

        # フォローアップより前だが服薬指導より後の日時
        report_time = COUNSELED_AT + timedelta(days=2)
        report = create_tracing_report(
            provided_at=report_time,
            follow_up_id=fu.id,
        )

        with pytest.raises(TracingReportDateBeforeFollowUpError):
            record.add_tracing_report(report)

    def test_add_tracing_report_with_duplicate_id_raises_error(self) -> None:
        """TC-DOM-08: 重複IDの追加は拒否される。"""
        record = _finalized_record()
        report = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))
        updated = record.add_tracing_report(report)

        with pytest.raises(DuplicatedTracingReportIdError):
            updated.add_tracing_report(report)

    def test_record_tracing_report_response_success(self) -> None:
        """TC-DOM-09: 処方医からの返答を正常に記録できる。"""
        record = _finalized_record()
        report = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))
        record_with_report = record.add_tracing_report(report)

        response = create_tracing_report_response(
            responded_at=COUNSELED_AT + timedelta(days=2),
            action_type=PrescriberActionType.AGREED_REFLECT_NEXT,
            content="次回処方時に減量します。",
            acknowledged_physician_name="山田太郎",
        )

        updated = record_with_report.record_tracing_report_response(report.id, response)

        assert len(updated.tracing_reports) == 1
        target_report = updated.tracing_reports[0]
        assert target_report.is_responded
        assert target_report.response is not None
        assert (
            target_report.response.action_type
            == PrescriberActionType.AGREED_REFLECT_NEXT
        )
        assert target_report.response.content.value == "次回処方時に減量します。"
        assert target_report.response.acknowledged_physician_name is not None
        assert target_report.response.acknowledged_physician_name.value == "山田太郎"
        # 元インスタンスは不変
        assert record_with_report.tracing_reports[0].response is None

    def test_record_response_to_unknown_report_raises_error(self) -> None:
        """TC-DOM-10: 存在しないレポートへの返答は拒否される。"""
        record = _finalized_record()
        report = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))
        record_with_report = record.add_tracing_report(report)

        response = create_tracing_report_response()
        other_report = create_tracing_report()

        with pytest.raises(TracingReportNotFoundError):
            record_with_report.record_tracing_report_response(other_report.id, response)

    def test_record_response_already_responded_raises_error(self) -> None:
        """TC-DOM-11: 既に返答済みのレポートへの再返答は拒否される。"""
        record = _finalized_record()
        report = create_tracing_report(provided_at=COUNSELED_AT + timedelta(days=1))
        record_with_report = record.add_tracing_report(report)

        response1 = create_tracing_report_response(
            responded_at=COUNSELED_AT + timedelta(days=2)
        )
        responded_record = record_with_report.record_tracing_report_response(
            report.id, response1
        )

        response2 = create_tracing_report_response(
            responded_at=COUNSELED_AT + timedelta(days=3)
        )
        with pytest.raises(TracingReportAlreadyRespondedError):
            responded_record.record_tracing_report_response(report.id, response2)

    def test_record_response_before_provided_date_raises_error(self) -> None:
        """TC-DOM-12: 提供日時より前の返答日時は拒否される。"""
        record = _finalized_record()
        provided_time = COUNSELED_AT + timedelta(days=3)
        report = create_tracing_report(provided_at=provided_time)
        record_with_report = record.add_tracing_report(report)

        # 提供より前の返答日時
        past_response_time = provided_time - timedelta(hours=1)
        response = create_tracing_report_response(responded_at=past_response_time)

        with pytest.raises(TracingReportResponseDateBeforeProvidedError):
            record_with_report.record_tracing_report_response(report.id, response)

    def test_tracing_report_enums_and_labels(self) -> None:
        """TC-DOM-13: 区分値のラベルが正しく定義されている。"""
        assert TracingReportCategory.RESIDUAL_DRUG.label == "残薬調整"
        assert (
            TracingReportCategory.ADVERSE_REACTION.label == "副作用疑い・モニタリング"
        )
        assert TracingReportCategory.ADHERENCE.label == "服薬状況・アドヒアランス"
        assert (
            TracingReportCategory.PRESCRIPTION_PROPOSAL.label
            == "処方提案・ポリファーマシー"
        )
        assert TracingReportCategory.PATIENT_CONSULTATION.label == "患者相談・生活状況"
        assert TracingReportCategory.OTHER.label == "その他"

        assert TracingReportFeeCategory.FEE_1.label == "服薬情報等提供料1"
        assert TracingReportFeeCategory.FEE_2.label == "服薬情報等提供料2"
        assert TracingReportFeeCategory.FEE_3.label == "服薬情報等提供料3"
        assert TracingReportFeeCategory.NONE.label == "算定なし"

        assert TracingReportDeliveryMethod.FAX.label == "FAX"
        assert TracingReportDeliveryMethod.MAIL.label == "郵送"
        assert TracingReportDeliveryMethod.ELECTRONIC.label == "電子"
        assert TracingReportDeliveryMethod.HAND_DELIVERY.label == "手渡し"

        assert PrescriberActionType.AGREED_REFLECT_NEXT.label == "次回処方に反映・変更"
        assert PrescriberActionType.MAINTAIN_CURRENT.label == "現状維持・継続観察"
        assert PrescriberActionType.EXAMINATION_REQUIRED.label == "追加検査・受診指示"
        assert PrescriberActionType.ACKNOWLEDGED.label == "確認・了解"

    def test_tracing_report_primitives_validation(self) -> None:
        """TC-DOM-14: テキストプリミティブのバリデーション。"""
        with pytest.raises(DomainValidationError, match="空にできません"):
            TracingReportContent("")

        with pytest.raises(DomainValidationError, match="2000文字以内"):
            TracingReportContent("a" * 2001)

        with pytest.raises(DomainValidationError, match="空にできません"):
            PhysicianName("")

        with pytest.raises(DomainValidationError, match="100文字以内"):
            PhysicianName("a" * 101)

        with pytest.raises(DomainValidationError, match="空にできません"):
            TracingReportResponseContent("")

        with pytest.raises(DomainValidationError, match="2000文字以内"):
            TracingReportResponseContent("a" * 2001)
