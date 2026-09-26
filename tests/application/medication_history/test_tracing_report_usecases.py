"""処方医への服薬情報等提供（トレーシングレポート）ユースケーステスト。"""

from datetime import timedelta

import pytest

from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.exceptions import MedicationHistoryNotFoundError
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.inputs import (
    RecordTracingReportCommand,
    RecordTracingReportResponseCommand,
)
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    TracingReportAlreadyRespondedError,
    TracingReportNotFoundError,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    TracingReportId,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_start_command,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_follow_up,
    create_independent_follow_up_record,
    finalize_record_with_review,
)


async def _create_and_finalize_record(fixture: MedicationHistoryFixture) -> str:
    """テスト用に確定済みの薬歴を作成してレコードID文字列を返す。"""
    draft = await fixture.start.execute(create_start_command(fixture))
    finalized = await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=draft.corporate_id,
            record_id=draft.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    return str(finalized.id)


class TestRecordTracingReportUseCase:
    """RecordTracingReportUseCase の単体・結合テスト。"""

    async def test_record_tracing_report_success(self) -> None:
        """TC-APP-01: 確定済み薬歴にトレーシングレポートを記録し、更新後DTOに反映される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = RecordTracingReportCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            reporter_id=str(fixture.counselor_id.value),
            provided_at=COUNSELED_AT + timedelta(days=1),
            medical_institution_name="総合医療センター",
            physician_name="山田太郎",
            category="residual_drug",
            fee_category="fee_2",
            delivery_method="fax",
            content="残薬調整の提案。",
        )

        dto = await fixture.record_tracing_report.execute(command)

        assert len(dto.tracing_reports) == 1
        rep = dto.tracing_reports[0]
        assert rep.reporter_id == str(fixture.counselor_id.value)
        assert rep.medical_institution_name == "総合医療センター"
        assert rep.physician_name == "山田太郎"
        assert rep.category == "residual_drug"
        assert rep.fee_category == "fee_2"
        assert rep.delivery_method == "fax"
        assert rep.content == "残薬調整の提案。"
        assert rep.response is None

        # 永続化された集約を直接確認
        loaded = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(record_id),
        )
        assert loaded is not None
        assert len(loaded.tracing_reports) == 1

    async def test_record_tracing_report_with_follow_up_success(self) -> None:
        """TC-APP-02: フォローアップIDを指定してトレーシングレポートを記録できる。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # 旧形式の内包フォローアップを残した薬歴を用意する。
        fu_time = COUNSELED_AT + timedelta(days=3)
        record = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(record_id),
        )
        assert record is not None
        follow_up = create_follow_up(followed_up_at=fu_time)
        await fixture.record_repository.save(record.add_follow_up(follow_up))
        follow_up_id = str(follow_up.id.value)

        command = RecordTracingReportCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            reporter_id=str(fixture.counselor_id.value),
            provided_at=fu_time + timedelta(hours=2),
            medical_institution_name="総合医療センター",
            physician_name="山田太郎",
            category="adverse_reaction",
            fee_category="fee_2",
            delivery_method="electronic",
            content="フォローアップで副作用の兆候を確認したため報告。",
            follow_up_id=follow_up_id,
        )

        dto = await fixture.record_tracing_report.execute(command)

        assert len(dto.tracing_reports) == 1
        assert dto.tracing_reports[0].follow_up_id == follow_up_id

    async def test_tc34_独立フォローアップのトレーシングレポートは自身の薬歴に属する(
        self,
    ) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert source is not None
        follow_up = finalize_record_with_review(
            create_independent_follow_up_record(
                source,
                counseled_at=COUNSELED_AT + timedelta(days=3),
                finalized=False,
            )
        )
        await fixture.record_repository.save(follow_up)

        dto = await fixture.record_tracing_report.execute(
            RecordTracingReportCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(follow_up.id.value),
                reporter_id=str(fixture.counselor_id.value),
                provided_at=COUNSELED_AT + timedelta(days=4),
                medical_institution_name="総合医療センター",
                physician_name="山田太郎",
                category="adverse_reaction",
                fee_category="fee_2",
                delivery_method="electronic",
                content="独立フォローアップ後に副作用を報告。",
            )
        )

        updated_follow_up = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=follow_up.id,
        )
        unchanged_source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert dto.id == str(follow_up.id.value)
        assert len(dto.tracing_reports) == 1
        assert dto.tracing_reports[0].follow_up_id is None
        assert updated_follow_up is not None
        assert len(updated_follow_up.tracing_reports) == 1
        assert unchanged_source is not None
        assert unchanged_source.tracing_reports == ()

    async def test_record_tracing_report_inactive_corporate_raises_error(self) -> None:
        """TC-APP-03: 非アクティブ法人の場合は拒否される。"""
        fixture = create_fixture()
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        command = RecordTracingReportCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(MedicationHistoryRecordId.generate().value),
            reporter_id=str(fixture.counselor_id.value),
            provided_at=COUNSELED_AT + timedelta(days=1),
            medical_institution_name="総合医療センター",
            physician_name="山田太郎",
            category="residual_drug",
            fee_category="fee_1",
            delivery_method="fax",
            content="残薬調整。",
        )

        with pytest.raises(CorporateInactiveError):
            await fixture.record_tracing_report.execute(command)

    async def test_record_tracing_report_record_not_found_raises_error(self) -> None:
        """TC-APP-04: 対象薬歴が存在しない場合は拒否される。"""
        fixture = create_fixture()
        unknown_record_id = str(MedicationHistoryRecordId.generate().value)

        command = RecordTracingReportCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=unknown_record_id,
            reporter_id=str(fixture.counselor_id.value),
            provided_at=COUNSELED_AT + timedelta(days=1),
            medical_institution_name="総合医療センター",
            physician_name="山田太郎",
            category="residual_drug",
            fee_category="fee_1",
            delivery_method="fax",
            content="残薬調整。",
        )

        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.record_tracing_report.execute(command)

    async def test_record_tracing_report_unqualified_staff_raises_error(self) -> None:
        """TC-APP-05: 報告者が薬剤師資格を持たない場合は拒否される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # 資格を持たないスタッフ
        unqualified_staff_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=unqualified_staff_id,
            qualifications=StaffQualifications(),  # 薬剤師なし
        )

        command = RecordTracingReportCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            reporter_id=str(unqualified_staff_id.value),
            provided_at=COUNSELED_AT + timedelta(days=1),
            medical_institution_name="総合医療センター",
            physician_name="山田太郎",
            category="residual_drug",
            fee_category="fee_1",
            delivery_method="fax",
            content="残薬調整。",
        )

        with pytest.raises(CounselorQualificationError):
            await fixture.record_tracing_report.execute(command)


class TestRecordTracingReportResponseUseCase:
    """RecordTracingReportResponseUseCase の単体・結合テスト。"""

    async def test_record_tracing_report_response_success(self) -> None:
        """TC-APP-06: 処方医からの返答を正常に記録し、DTOに反映される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # レポートを追加
        report_dto = await fixture.record_tracing_report.execute(
            RecordTracingReportCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
                reporter_id=str(fixture.counselor_id.value),
                provided_at=COUNSELED_AT + timedelta(days=1),
                medical_institution_name="総合医療センター",
                physician_name="山田太郎",
                category="residual_drug",
                fee_category="fee_2",
                delivery_method="fax",
                content="残薬調整。",
            )
        )
        report_id = report_dto.tracing_reports[0].id

        receiver_id = StaffId.generate()
        response_cmd = RecordTracingReportResponseCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            tracing_report_id=report_id,
            responded_at=COUNSELED_AT + timedelta(days=2),
            content="次回処方で減量します。",
            action_type="agreed_reflect_next",
            received_by=str(receiver_id.value),
            acknowledged_physician_name="山田太郎",
        )

        updated_dto = await fixture.record_tracing_report_response.execute(response_cmd)

        assert len(updated_dto.tracing_reports) == 1
        rep = updated_dto.tracing_reports[0]
        assert rep.response is not None
        assert rep.response.content == "次回処方で減量します。"
        assert rep.response.action_type == "agreed_reflect_next"
        assert rep.response.received_by == str(receiver_id.value)
        assert rep.response.acknowledged_physician_name == "山田太郎"

        # 永続化された集約を直接確認
        loaded = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(record_id),
        )
        assert loaded is not None
        assert loaded.tracing_reports[0].response is not None

    async def test_record_response_inactive_corporate_raises_error(self) -> None:
        """TC-APP-07: 非アクティブ法人の場合は拒否される。"""
        fixture = create_fixture()
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        response_cmd = RecordTracingReportResponseCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(MedicationHistoryRecordId.generate().value),
            tracing_report_id=str(TracingReportId.generate().value),
            responded_at=COUNSELED_AT + timedelta(days=2),
            content="了解しました。",
            action_type="acknowledged",
            received_by=str(StaffId.generate().value),
        )

        with pytest.raises(CorporateInactiveError):
            await fixture.record_tracing_report_response.execute(response_cmd)

    async def test_record_response_not_found_raises_error(self) -> None:
        """TC-APP-08: 薬歴またはレポートが見つからない場合は拒否される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # 存在しない薬歴ID
        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.record_tracing_report_response.execute(
                RecordTracingReportResponseCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(MedicationHistoryRecordId.generate().value),
                    tracing_report_id=str(TracingReportId.generate().value),
                    responded_at=COUNSELED_AT + timedelta(days=2),
                    content="了解。",
                    action_type="acknowledged",
                    received_by=str(StaffId.generate().value),
                )
            )

        # 存在しないレポートID
        with pytest.raises(TracingReportNotFoundError):
            await fixture.record_tracing_report_response.execute(
                RecordTracingReportResponseCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=record_id,
                    tracing_report_id=str(TracingReportId.generate().value),
                    responded_at=COUNSELED_AT + timedelta(days=2),
                    content="了解。",
                    action_type="acknowledged",
                    received_by=str(StaffId.generate().value),
                )
            )

    async def test_record_response_already_responded_raises_error(self) -> None:
        """TC-APP-09: 既に返答済みのレポートに再度返答しようとすると拒否される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        report_dto = await fixture.record_tracing_report.execute(
            RecordTracingReportCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
                reporter_id=str(fixture.counselor_id.value),
                provided_at=COUNSELED_AT + timedelta(days=1),
                medical_institution_name="総合医療センター",
                physician_name="山田太郎",
                category="residual_drug",
                fee_category="fee_2",
                delivery_method="fax",
                content="残薬調整。",
            )
        )
        report_id = report_dto.tracing_reports[0].id

        response_cmd = RecordTracingReportResponseCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            tracing_report_id=report_id,
            responded_at=COUNSELED_AT + timedelta(days=2),
            content="次回処方で減量します。",
            action_type="agreed_reflect_next",
            received_by=str(StaffId.generate().value),
        )
        await fixture.record_tracing_report_response.execute(response_cmd)

        # 再度返答
        with pytest.raises(TracingReportAlreadyRespondedError):
            await fixture.record_tracing_report_response.execute(response_cmd)
