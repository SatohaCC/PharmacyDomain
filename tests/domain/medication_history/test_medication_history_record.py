"""薬歴指導記録集約のテスト。

法定記載事項（保険調剤の理解のために 令和8年度 第2節 通則(4)）のうち、
集約が単独で判定できるものを固定する。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import (
    FinalizationDateBeforeCounselingError,
    FinalizationDelayReasonRequiredError,
    FinalizationStaffRequiredError,
    HandbookGuidanceRequiredError,
    HandbookReasonNotAllowedError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryUnassessedItemsError,
    ResidualDrugDetailNotAllowedError,
    ResidualDrugDetailRequiredError,
    SoapContentRequiredError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    AmendmentReason,
    AmendmentTimestamp,
    BillingAdditionCode,
    BillingAdditionName,
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    HandbookConsolidationReason,
    HandbookNotPresentedReason,
    MajorCategoryCode,
    MedicationHistoryReviewResult,
    MedicationHistoryReviewTimestamp,
    MedicationHistoryStatus,
    MediumCategoryCode,
    ResidualDrugQuantity,
    ResidualDrugReason,
    StatutoryCategory,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    HandbookStatus,
    ResidualDrugRecord,
    SoapRecord,
)
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    create_note,
    create_nsips_draft_record,
    create_record,
    create_soap,
    finalize_record_with_review,
)

_AMENDED_AT = AmendmentTimestamp(datetime(2026, 8, 25, 1, 0, tzinfo=UTC))
_REASON = AmendmentReason("記載漏れがあったため追記した。")


def _record_counseled_at(record: MedicationHistoryRecord) -> CounselingTimestamp:
    """通常のテストレコードが持つ指導日時を返す。"""
    assert record.counseled_at is not None
    return record.counseled_at


def _record_counselor_id(record: MedicationHistoryRecord) -> StaffId:
    """通常のテストレコードが持つ指導者を返す。"""
    assert record.counselor_id is not None
    return record.counselor_id


class TestNSIPS取込と服薬指導実績:
    """取込メタデータと実際の服薬指導を別の事実として保持する。"""

    def test_tc01_NSIPS取込下書きは_取込時刻だけで構築できる(self) -> None:
        imported_at = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)

        actual = create_nsips_draft_record(imported_at=imported_at)

        assert actual.status == MedicationHistoryStatus.DRAFT
        assert actual.counselor_id is None
        assert actual.counseled_at is None
        assert actual.imported_at is not None
        assert actual.imported_at.value == imported_at

    @pytest.mark.parametrize(
        "field_name",
        ("counselor", "counseled_at"),
    )
    def test_tc02_指導者と指導日時は_片方だけ設定できない(
        self, field_name: str
    ) -> None:
        record = create_nsips_draft_record()

        with pytest.raises(MedicationHistoryDomainError):
            if field_name == "counselor":
                replace(record, counselor_id=StaffId.generate())
            else:
                replace(
                    record,
                    counseled_at=CounselingTimestamp(
                        datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
                    ),
                )

    def test_tc03_指導実績も取込時刻もない下書きは_構築できない(self) -> None:
        record = create_nsips_draft_record()

        with pytest.raises(MedicationHistoryDomainError):
            replace(record, imported_at=None)

    def test_tc04_取込時刻だけの下書きは_指導情報なしで確定できない(self) -> None:
        record = create_nsips_draft_record()

        with pytest.raises(MedicationHistoryDomainError):
            finalize_record_with_review(record)

    def test_tc05_実指導情報を設定して確定しても_取込時刻を維持する(self) -> None:
        imported_at = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
        counseled_at = datetime(2026, 8, 24, 5, 0, tzinfo=UTC)
        counselor_id = StaffId.generate()
        record = create_nsips_draft_record(
            imported_at=imported_at, ready_to_finalize=True
        )

        finalized = finalize_record_with_review(
            record,
            counselor_id=counselor_id,
            counseled_at=CounselingTimestamp(counseled_at),
        )

        assert finalized.counselor_id == counselor_id
        assert finalized.counseled_at == CounselingTimestamp(counseled_at)
        assert finalized.imported_at is not None
        assert finalized.imported_at.value == imported_at


class Test残薬状況:
    """法定記載事項ウ（ホ）の残薬状況を検証する。"""

    def test_残薬なしを_明示的に記録できる(self) -> None:
        """「残薬がないときは、その旨を記載すること」。

        ``Optional`` にすると「聞き忘れ」と「残薬なし」が同じ ``None`` になる。
        """
        # Arrange / Act
        actual = ResidualDrugRecord.none_remaining()

        # Assert
        assert not actual.has_residual_drugs
        assert actual.quantity is None

    def test_残薬ありなのに数量が無いと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ResidualDrugDetailRequiredError):
            ResidualDrugRecord(
                has_residual_drugs=True,
                reason=ResidualDrugReason("飲み忘れが続いたため。"),
            )

    def test_残薬ありなのに理由が無いと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ResidualDrugDetailRequiredError):
            ResidualDrugRecord(
                has_residual_drugs=True, quantity=ResidualDrugQuantity(5)
            )

    def test_残薬なしなのに数量があると_構築できない(self) -> None:
        """矛盾した記録を残さない。"""
        # Arrange / Act / Assert
        with pytest.raises(ResidualDrugDetailNotAllowedError):
            ResidualDrugRecord(
                has_residual_drugs=False, quantity=ResidualDrugQuantity(5)
            )

    def test_残薬ありで数量と理由が揃えば_構築できる(self) -> None:
        # Arrange / Act
        actual = ResidualDrugRecord(
            has_residual_drugs=True,
            quantity=ResidualDrugQuantity(5),
            reason=ResidualDrugReason("飲み忘れが続いたため。"),
        )

        # Assert
        assert actual.has_residual_drugs
        assert actual.quantity == ResidualDrugQuantity(5)


class Testお薬手帳:
    """法定記載事項ウ（ト）のお薬手帳活用状況を検証する。"""

    def test_未活用なのに理由が無いと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(HandbookGuidanceRequiredError):
            HandbookStatus(presented=False, guidance_provided=True)

    def test_未活用なのに指導の有無が無いと_構築できない(self) -> None:
        """「活用しなかった場合はその理由と患者への指導の有無」。"""
        # Arrange / Act / Assert
        with pytest.raises(HandbookGuidanceRequiredError):
            HandbookStatus(
                presented=False,
                not_presented_reason=HandbookNotPresentedReason("持参忘れ。"),
            )

    def test_活用したのに未活用の理由があると_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(HandbookReasonNotAllowedError):
            HandbookStatus(
                presented=True,
                not_presented_reason=HandbookNotPresentedReason("持参忘れ。"),
            )

    def test_指導しなかったことも_記録できる(self) -> None:
        """``guidance_provided`` は有無を表すので ``False`` も正当な記録。"""
        # Arrange / Act
        actual = HandbookStatus(
            presented=False,
            not_presented_reason=HandbookNotPresentedReason("手帳不要の意向。"),
            guidance_provided=False,
        )

        # Assert
        assert actual.guidance_provided is False

    def test_複数手帳を統合しなかった理由も_記録できる(self) -> None:
        # Arrange / Act
        actual = HandbookStatus(
            presented=True,
            multiple_handbooks_not_consolidated_reason=HandbookConsolidationReason(
                "患者が病院ごとに分けたいと希望したため。"
            ),
        )

        # Assert
        assert actual.multiple_handbooks_not_consolidated_reason is not None


class TestSOAPと確定:
    """下書きの編集とSOAPを満たした確定を検証する。"""

    def test_tc21_確認済み否定値と未記録を区別する(self) -> None:
        """確認済みの否定値はNoneの未記録状態と異なる値で保持する。"""
        assessed = create_record(information_sheet_provided=False)
        unassessed = replace(
            assessed,
            method=None,
            handbook_status=None,
            residual_drug=None,
            information_sheet_provided=None,
        )

        assert assessed.information_sheet_provided is False
        assert assessed.residual_drug is not None
        assert assessed.residual_drug.has_residual_drugs is False
        assert unassessed.method is None
        assert unassessed.handbook_status is None
        assert unassessed.residual_drug is None
        assert unassessed.information_sheet_provided is None

    def test_tc22_必須事項が未確認の薬歴を確定できず確認後は確定できる(
        self,
    ) -> None:
        """未確認項目を列挙して止め、下書きで確認後に確定できる。"""
        unassessed = replace(
            create_record(information_sheet_provided=None),
            method=None,
            handbook_status=None,
            residual_drug=None,
        )

        with pytest.raises(MedicationHistoryUnassessedItemsError) as error:
            finalize_record_with_review(unassessed)

        assert error.value.missing_items == (
            "服薬指導方法",
            "お薬手帳の活用状況",
            "残薬状況",
            "情報提供文書の交付",
        )
        completed = unassessed.update_draft(
            method=CounselingMethod.FACE_TO_FACE,
            handbook_status=HandbookStatus(presented=True),
            residual_drug=ResidualDrugRecord.none_remaining(),
            information_sheet_provided=False,
        )
        assert finalize_record_with_review(completed).is_finalized

    def test_下書きでは_SOAPが空でも構築できる(self) -> None:
        """聞き取りながら書き足す運用を壊さない。"""
        # Arrange / Act
        actual = create_record(soap=SoapRecord())

        # Assert
        assert actual.status is MedicationHistoryStatus.DRAFT

    def test_finalize_with_partial_soap_s_only(self) -> None:
        """S節だけでは薬剤師の評価・指導を確認できず確定できない。"""
        soap = SoapRecord(subjective=(create_note("頭痛があるとのこと。"),))
        record = create_record(soap=soap)
        with pytest.raises(MedicationHistoryDomainError):
            finalize_record_with_review(record)
        assert not record.is_finalized

    def test_finalize_with_s_and_p(self) -> None:
        """TC-REC-02: SとP節のみでも正常に確定できること。"""
        soap = SoapRecord(
            subjective=(create_note("頭痛改善したとのこと。"),),
            plan=(create_note("次回経過観察。"),),
        )
        record = create_record(soap=soap)
        finalized = finalize_record_with_review(record)
        assert finalized.is_finalized

    def test_tc17_AssessmentとPlanを含む確定でレビュー証跡を保持する(self) -> None:
        record = create_record()
        reviewer_id = StaffId.generate()
        reviewed_at = MedicationHistoryReviewTimestamp(
            _record_counseled_at(record).value
        )

        finalized = record.finalize(
            review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
            reviewed_by=reviewer_id,
            reviewed_at=reviewed_at,
        )

        assert finalized.review_result is (
            MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED
        )
        assert finalized.reviewed_by == reviewer_id
        assert finalized.reviewed_at == reviewed_at

    def test_tc18_追加記載なしの明示確認結果を保存する(self) -> None:
        record = create_record(
            soap=SoapRecord(
                assessment=(create_note("対象情報を確認し、追加記載事項はない。"),)
            )
        )
        reviewed_at = MedicationHistoryReviewTimestamp(
            _record_counseled_at(record).value
        )

        finalized = record.finalize(
            review_result=MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS,
            reviewed_by=_record_counselor_id(record),
            reviewed_at=reviewed_at,
        )

        assert finalized.review_result is (
            MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS
        )
        assert finalized.reviewed_at == reviewed_at

    def test_tc19_レビュー結果がない薬歴は確定できない(self) -> None:
        record = create_record()

        with pytest.raises(MedicationHistoryDomainError):
            record.finalize()

        assert record.status is MedicationHistoryStatus.DRAFT

    def test_tc20_ObjectiveだけではAssessmentAndInstructionRecordedにできない(
        self,
    ) -> None:
        record = create_record(
            soap=SoapRecord(objective=(create_note("受信処方の要約。"),))
        )

        with pytest.raises(MedicationHistoryDomainError):
            record.finalize(
                review_result=(
                    MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED
                ),
                reviewed_by=_record_counselor_id(record),
                reviewed_at=MedicationHistoryReviewTimestamp(
                    _record_counseled_at(record).value
                ),
            )

        assert record.status is MedicationHistoryStatus.DRAFT

    def test_finalize_with_completely_empty_content_rejected(self) -> None:
        """TC-REC-04: SOAP全節が空かつ追加メモもない白紙確定は拒否されること。"""
        record = create_record(soap=SoapRecord())
        with pytest.raises(SoapContentRequiredError):
            finalize_record_with_review(record)

    def test_finalize_with_additional_notes_only(self) -> None:
        """SOAPの評価・指導が無い追加記載メモだけでは確定できない。"""
        record = create_record(
            soap=SoapRecord(),
            additional_notes=(
                CategorizedNote(
                    major_category_code=MajorCategoryCode("statutory"),
                    medium_category_code=MediumCategoryCode("concurrent_medication"),
                    text=CounselingNote("他院でロキソニン処方あり。"),
                ),
            ),
        )
        with pytest.raises(MedicationHistoryDomainError):
            finalize_record_with_review(record)
        assert not record.is_finalized

    def test_空文字だけの記載は_記載とみなさない(self) -> None:
        """定型文の空欄を埋めただけの記録（中身なし）は確定させない。"""
        record = create_record(
            soap=SoapRecord(
                subjective=(create_note("   "),),
            )
        )
        with pytest.raises(SoapContentRequiredError):
            finalize_record_with_review(record)

    def test_全セクションが埋まっていれば_確定できる(self) -> None:
        # Arrange
        record = create_record()

        # Act
        actual = finalize_record_with_review(record)

        # Assert
        assert actual.is_finalized

    def test_確定済は_下書きのSOAPを上書きできない(self) -> None:
        """調剤録は3年保存。遡って書き換えられる記録は監査に耐えない。"""
        # Arrange
        record = finalize_record_with_review(create_record())

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            record.update_draft_soap(create_soap(subjective="修正後の主観的情報。"))

    def test_確定済は_二度確定できない(self) -> None:
        # Arrange
        record = finalize_record_with_review(create_record())

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            record.finalize()

    def test_下書きなら_SOAPを差し替えられる(self) -> None:
        # Arrange
        record = create_record()

        # Act
        actual = record.update_draft_soap(create_soap(subjective="聞き直した内容。"))

        # Assert
        assert actual.soap.subjective[0].text.value == "聞き直した内容。"


class Test追記:
    """確定済の修正は追記のみ。"""

    def test_未確定には_追記できない(self) -> None:
        # Arrange
        record = create_record()

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFinalizedError):
            record.amend(
                amended_soap=create_soap(),
                reason=_REASON,
                amended_by=StaffId.generate(),
                amended_at=_AMENDED_AT,
            )

    def test_追記しても_元のSOAPは書き換わらない(self) -> None:
        # Arrange
        record = finalize_record_with_review(
            create_record(soap=create_soap(subjective="交付時の記載。"))
        )

        # Act
        actual = record.amend(
            amended_soap=create_soap(subjective="追記後の記載。"),
            reason=_REASON,
            amended_by=StaffId.generate(),
            amended_at=_AMENDED_AT,
        )

        # Assert
        assert actual.soap.subjective[0].text.value == "交付時の記載。"
        assert actual.effective_soap.subjective[0].text.value == "追記後の記載。"
        assert len(actual.amendments) == 1

    def test_空セクションのあるSOAPは_追記できない(self) -> None:
        """確定済の薬歴を白紙にする追記は拒否されること（TC-REC-06）。"""
        # Arrange
        record = finalize_record_with_review(create_record())

        # Act / Assert
        with pytest.raises(SoapContentRequiredError):
            record.amend(
                amended_soap=SoapRecord(),
                reason=_REASON,
                amended_by=StaffId.generate(),
                amended_at=_AMENDED_AT,
            )

    def test_実効SOAPが空になる確定済の薬歴は_構築できない(self) -> None:
        """白紙の確定済薬歴はreplaceでも構築できない。"""
        # Arrange: 追記の中身だけを空へ差し替えた状態を組み立てる
        record = finalize_record_with_review(create_record())
        amended = record.amend(
            amended_soap=create_soap(),
            reason=_REASON,
            amended_by=StaffId.generate(),
            amended_at=_AMENDED_AT,
        )
        emptied = replace(amended.amendments[0], amended_soap=SoapRecord())

        # Act / Assert
        with pytest.raises(SoapContentRequiredError):
            replace(amended, amendments=(emptied,))

    def test_amend_with_partial_soap(self) -> None:
        """TC-REC-07: Sのみの部分記載で追記できること。"""
        record = finalize_record_with_review(create_record())
        amended = record.amend(
            amended_soap=SoapRecord(subjective=(create_note("追記: 頭痛再発。"),)),
            reason=_REASON,
            amended_by=StaffId.generate(),
            amended_at=_AMENDED_AT,
        )
        assert amended.effective_soap.subjective[0].text.value == "追記: 頭痛再発。"

    def test_追記は_確定済の薬歴にだけ付く(self) -> None:
        """追記だけを持つ下書きは構築できない。"""
        # Arrange
        record = finalize_record_with_review(create_record())
        amended = record.amend(
            amended_soap=create_soap(),
            reason=_REASON,
            amended_by=StaffId.generate(),
            amended_at=_AMENDED_AT,
        )

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFinalizedError):
            type(amended)(
                id=amended.id,
                corporate_id=amended.corporate_id,
                store_id=amended.store_id,
                patient_id=amended.patient_id,
                dispensing_id=amended.dispensing_id,
                prescription_id=amended.prescription_id,
                counselor_id=amended.counselor_id,
                counseled_at=amended.counseled_at,
                method=amended.method,
                soap=amended.soap,
                handbook_status=amended.handbook_status,
                residual_drug=amended.residual_drug,
                status=MedicationHistoryStatus.DRAFT,
                amendments=amended.amendments,
            )


class Test法定カテゴリ:
    """個別指導で項目別に示せること。"""

    def test_カテゴリを指定して_SOAP横断で抽出できる(self) -> None:
        # Arrange
        record = create_record()

        # Act
        actual = record.soap.notes_of(StatutoryCategory.MEDICATION_ADHERENCE)

        # Assert
        assert len(actual) == 1
        assert actual[0].text.value == "飲み忘れは週に1回程度とのこと。"

    def test_該当が無いカテゴリは_空で返る(self) -> None:
        # Arrange
        record = create_record()

        # Act / Assert
        assert record.soap.notes_of(StatutoryCategory.RESIDUAL_DRUG) == ()

    def test_全カテゴリに_日本語ラベルがある(self) -> None:
        # Arrange / Act / Assert
        for category in StatutoryCategory:
            assert category.label


class Test確定プリミティブ:
    """TC-01 〜 TC-04: 確定日時および記載遅延理由プリミティブの検証。"""

    def test_tc01_確定日時は_タイムゾーン付き日時で生成できる(self) -> None:
        # Arrange / Act
        now = datetime.now(UTC)
        ts = FinalizedTimestamp(now)

        # Assert
        assert ts.value == now

    def test_tc02_確定日時に_タイムゾーンが無いと拒否される(self) -> None:
        # Arrange / Act / Assert
        naive = datetime(2026, 9, 21, 10, 0, 0)  # noqa: DTZ001
        with pytest.raises(DomainValidationError):
            FinalizedTimestamp(naive)

    def test_tc03_遅延理由は_正常な文字列で生成できる(self) -> None:
        # Arrange / Act
        reason = FinalizationDelayReason("救急当直および処方疑義照会対応のため翌日記載")

        # Assert
        assert reason.value == "救急当直および処方疑義照会対応のため翌日記載"

    def test_tc04_遅延理由は_空文字で拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError):
            FinalizationDelayReason("")


class Test下書き更新:
    """TC-05 〜 TC-07: 下書き状態の全項目更新機能の検証。"""

    def test_tc05_下書き薬歴の全項目を一括更新できる(self) -> None:
        # Arrange
        record = create_record()
        new_handbook = HandbookStatus(presented=True)
        new_residual = ResidualDrugRecord.none_remaining()
        new_soap = create_soap()
        new_note = CategorizedNote(
            major_category_code=MajorCategoryCode("soap"),
            medium_category_code=MediumCategoryCode("s"),
            text=CounselingNote("下書き更新メモ"),
        )

        # Act
        updated = record.update_draft(
            handbook_status=new_handbook,
            residual_drug=new_residual,
            soap=new_soap,
            information_sheet_provided=True,
            additional_notes=(new_note,),
        )

        # Assert
        assert updated.handbook_status == new_handbook
        assert updated.residual_drug == new_residual
        assert updated.information_sheet_provided is True
        assert updated.additional_notes == (new_note,)
        assert updated.status == MedicationHistoryStatus.DRAFT

    def test_tc06_下書き薬歴の一部項目のみ更新できる(self) -> None:
        # Arrange
        record = create_record()
        orig_soap = record.soap
        new_handbook = HandbookStatus(presented=True)

        # Act
        updated = record.update_draft(handbook_status=new_handbook)

        # Assert
        assert updated.handbook_status == new_handbook
        assert updated.soap == orig_soap

    def test_tc07_確定済みの薬歴に対して下書き更新を呼ぶと拒否される(self) -> None:
        # Arrange
        record = create_record()
        finalized = record.finalize(
            finalized_at=FinalizedTimestamp(_record_counseled_at(record).value),
            finalized_by=_record_counselor_id(record),
            review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
            reviewed_by=_record_counselor_id(record),
            reviewed_at=MedicationHistoryReviewTimestamp(
                _record_counseled_at(record).value
            ),
        )

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            finalized.update_draft(information_sheet_provided=True)


class Test確定真正性と遅延理由:
    """TC-08 〜 TC-14: 確定メタデータ、当日記載原則、遅延理由の検証。"""

    def test_tc08_当日確定で確定日時と確定者が記録される(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(_record_counseled_at(record).value)
        finalized_by = StaffId.generate()

        # Act
        finalized = finalize_record_with_review(
            record,
            finalized_at=finalized_at,
            finalized_by=finalized_by,
        )

        # Assert
        assert finalized.is_finalized
        assert finalized.finalized_at == finalized_at
        assert finalized.finalized_by == finalized_by
        assert finalized.delay_reason is None

    def test_tc09_翌日確定で遅延理由を指定して確定できる(self) -> None:
        # Arrange
        record = create_record()
        counseled_at = _record_counseled_at(record).value
        next_day = counseled_at.replace(day=counseled_at.day + 1)
        finalized_at = FinalizedTimestamp(next_day)
        finalized_by = StaffId.generate()
        delay_reason = FinalizationDelayReason("疑義照会の回答待ちのため翌日記載")

        # Act
        finalized = finalize_record_with_review(
            record,
            finalized_at=finalized_at,
            finalized_by=finalized_by,
            delay_reason=delay_reason,
        )

        # Assert
        assert finalized.is_finalized
        assert finalized.delay_reason == delay_reason

    def test_tc10_翌日確定で遅延理由が無いと拒否される(self) -> None:
        # Arrange
        record = create_record()
        counseled_at = _record_counseled_at(record).value
        next_day = counseled_at.replace(day=counseled_at.day + 1)
        finalized_at = FinalizedTimestamp(next_day)
        finalized_by = StaffId.generate()

        # Act / Assert
        with pytest.raises(FinalizationDelayReasonRequiredError):
            finalize_record_with_review(
                record,
                finalized_at=finalized_at,
                finalized_by=finalized_by,
                delay_reason=None,
            )

    def test_tc11_指導日時より過去の確定日時は拒否される(self) -> None:
        # Arrange
        record = create_record()
        counseled_at = _record_counseled_at(record).value
        past = counseled_at.replace(year=counseled_at.year - 1)
        finalized_at = FinalizedTimestamp(past)
        finalized_by = StaffId.generate()

        # Act / Assert
        with pytest.raises(FinalizationDateBeforeCounselingError):
            finalize_record_with_review(
                record,
                finalized_at=finalized_at,
                finalized_by=finalized_by,
            )

    def test_tc13_確定状態で確定者が欠落していると不変条件違反(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(_record_counseled_at(record).value)

        # Act / Assert
        finalized = finalize_record_with_review(record, finalized_at=finalized_at)
        with pytest.raises(FinalizationStaffRequiredError):
            replace(finalized, finalized_by=None)

    def test_tc14_下書き状態で確定日時が設定されていると不変条件違反(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(_record_counseled_at(record).value)

        # Act / Assert
        with pytest.raises(MedicationHistoryDomainError):
            replace(
                record,
                status=MedicationHistoryStatus.DRAFT,
                finalized_at=finalized_at,
            )

    def test_算定加算情報を保持でき既定値は空タプル(self) -> None:
        """BillingAdditionを指定した記録が保持され、既定値は空になる。"""
        addition = BillingAddition(
            code=BillingAdditionCode("140000110"),
            name=BillingAdditionName("特定薬剤管理指導加算２"),
            points=100,
            quantity=2,
        )
        record = create_record(billing_additions=(addition,))
        assert len(record.billing_additions) == 1
        assert record.billing_additions[0].code.value == "140000110"
        assert record.billing_additions[0].name.value == "特定薬剤管理指導加算２"
        assert record.billing_additions[0].points == 100
        assert record.billing_additions[0].quantity == 2

        default_record = create_record()
        assert default_record.billing_additions == ()

    def test_tc29_加算は下書きだけ更新でき確定後は拒否する(self) -> None:
        """加算情報を下書きで置換でき、確定済み記録は凍結する。"""
        original = BillingAddition(
            code=BillingAdditionCode("140000110"),
            name=BillingAdditionName("加算A"),
            points=100,
            quantity=1,
        )
        corrected = BillingAddition(
            code=BillingAdditionCode("140000210"),
            name=BillingAdditionName("加算B"),
            points=200,
            quantity=2,
        )
        updated = create_record(billing_additions=(original,)).update_draft(
            billing_additions=(corrected,)
        )

        assert updated.billing_additions == (corrected,)
        finalized = finalize_record_with_review(updated)
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            finalized.update_draft(billing_additions=(original,))


@pytest.mark.parametrize("value", ("", "   "))
@pytest.mark.parametrize("primitive_name", ("code", "name"))
def test_tc30_算定加算Primitiveの空値を拒否する(
    value: str,
    primitive_name: str,
) -> None:
    """コード・名称Primitiveで親の非空検証が保たれる。"""
    from app.domain.medication_history.primitives import (
        BillingAdditionCode,
        BillingAdditionName,
    )

    primitive_type = (
        BillingAdditionCode if primitive_name == "code" else BillingAdditionName
    )

    with pytest.raises(DomainValidationError):
        primitive_type(value)
