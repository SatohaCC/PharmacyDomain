"""薬歴指導記録集約のテスト。

法定記載事項（保険調剤の理解のために 令和8年度 第2節 通則(4)）のうち、
集約が単独で判定できるものを固定する。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history import (
    AmendmentReason,
    AmendmentTimestamp,
    CategorizedNote,
    CounselingNote,
    FinalizationDateBeforeCounselingError,
    FinalizationDelayReason,
    FinalizationDelayReasonRequiredError,
    FinalizationStaffRequiredError,
    FinalizedTimestamp,
    HandbookConsolidationReason,
    HandbookGuidanceRequiredError,
    HandbookNotPresentedReason,
    HandbookReasonNotAllowedError,
    HandbookStatus,
    MajorCategoryCode,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryStatus,
    MediumCategoryCode,
    ResidualDrugDetailNotAllowedError,
    ResidualDrugDetailRequiredError,
    ResidualDrugQuantity,
    ResidualDrugReason,
    ResidualDrugRecord,
    SoapContentRequiredError,
    SoapRecord,
    StatutoryCategory,
)
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    create_note,
    create_record,
    create_soap,
)

_AMENDED_AT = AmendmentTimestamp(datetime(2026, 8, 25, 1, 0, tzinfo=UTC))
_REASON = AmendmentReason("記載漏れがあったため追記した。")


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

    def test_下書きでは_SOAPが空でも構築できる(self) -> None:
        """聞き取りながら書き足す運用を壊さない。"""
        # Arrange / Act
        actual = create_record(soap=SoapRecord())

        # Assert
        assert actual.status is MedicationHistoryStatus.DRAFT

    def test_finalize_with_partial_soap_s_only(self) -> None:
        """TC-REC-01: S節のみでも正常に確定できること。"""
        soap = SoapRecord(subjective=(create_note("頭痛があるとのこと。"),))
        record = create_record(soap=soap)
        finalized = record.finalize()
        assert finalized.is_finalized

    def test_finalize_with_s_and_p(self) -> None:
        """TC-REC-02: SとP節のみでも正常に確定できること。"""
        soap = SoapRecord(
            subjective=(create_note("頭痛改善したとのこと。"),),
            plan=(create_note("次回経過観察。"),),
        )
        record = create_record(soap=soap)
        finalized = record.finalize()
        assert finalized.is_finalized

    def test_finalize_with_completely_empty_content_rejected(self) -> None:
        """TC-REC-04: SOAP全節が空かつ追加メモもない白紙確定は拒否されること。"""
        record = create_record(soap=SoapRecord())
        with pytest.raises(SoapContentRequiredError):
            record.finalize()

    def test_finalize_with_additional_notes_only(self) -> None:
        """TC-REC-05: SOAPの4枠は空だが追加中区分メモがある場合は確定できること。"""
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
        finalized = record.finalize()
        assert finalized.is_finalized

    def test_空文字だけの記載は_記載とみなさない(self) -> None:
        """定型文の空欄を埋めただけの記録（中身なし）は確定させない。"""
        record = create_record(
            soap=SoapRecord(
                subjective=(create_note("   "),),
            )
        )
        with pytest.raises(SoapContentRequiredError):
            record.finalize()

    def test_全セクションが埋まっていれば_確定できる(self) -> None:
        # Arrange
        record = create_record()

        # Act
        actual = record.finalize()

        # Assert
        assert actual.is_finalized

    def test_確定済は_下書きのSOAPを上書きできない(self) -> None:
        """調剤録は3年保存。遡って書き換えられる記録は監査に耐えない。"""
        # Arrange
        record = create_record().finalize()

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            record.update_draft_soap(create_soap(subjective="修正後の主観的情報。"))

    def test_確定済は_二度確定できない(self) -> None:
        # Arrange
        record = create_record().finalize()

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
        record = create_record(soap=create_soap(subjective="交付時の記載。")).finalize()

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
        record = create_record().finalize()

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
        record = create_record().finalize()
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
        record = create_record().finalize()
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
        record = create_record().finalize()
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
            finalized_at=FinalizedTimestamp(record.counseled_at.value),
            finalized_by=record.counselor_id,
        )

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            finalized.update_draft(information_sheet_provided=True)


class Test確定真正性と遅延理由:
    """TC-08 〜 TC-14: 確定メタデータ、当日記載原則、遅延理由の検証。"""

    def test_tc08_当日確定で確定日時と確定者が記録される(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(record.counseled_at.value)
        finalized_by = StaffId.generate()

        # Act
        finalized = record.finalize(
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
        next_day = record.counseled_at.value.replace(
            day=record.counseled_at.value.day + 1
        )
        finalized_at = FinalizedTimestamp(next_day)
        finalized_by = StaffId.generate()
        delay_reason = FinalizationDelayReason("疑義照会の回答待ちのため翌日記載")

        # Act
        finalized = record.finalize(
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
        next_day = record.counseled_at.value.replace(
            day=record.counseled_at.value.day + 1
        )
        finalized_at = FinalizedTimestamp(next_day)
        finalized_by = StaffId.generate()

        # Act / Assert
        with pytest.raises(FinalizationDelayReasonRequiredError):
            record.finalize(
                finalized_at=finalized_at,
                finalized_by=finalized_by,
                delay_reason=None,
            )

    def test_tc11_指導日時より過去の確定日時は拒否される(self) -> None:
        # Arrange
        record = create_record()
        past = record.counseled_at.value.replace(
            year=record.counseled_at.value.year - 1
        )
        finalized_at = FinalizedTimestamp(past)
        finalized_by = StaffId.generate()

        # Act / Assert
        with pytest.raises(FinalizationDateBeforeCounselingError):
            record.finalize(
                finalized_at=finalized_at,
                finalized_by=finalized_by,
            )

    def test_tc13_確定状態で確定者が欠落していると不変条件違反(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(record.counseled_at.value)

        # Act / Assert
        with pytest.raises(FinalizationStaffRequiredError):
            replace(
                record,
                status=MedicationHistoryStatus.FINALIZED,
                finalized_at=finalized_at,
                finalized_by=None,
            )

    def test_tc14_下書き状態で確定日時が設定されていると不変条件違反(self) -> None:
        # Arrange
        record = create_record()
        finalized_at = FinalizedTimestamp(record.counseled_at.value)

        # Act / Assert
        with pytest.raises(MedicationHistoryDomainError):
            replace(
                record,
                status=MedicationHistoryStatus.DRAFT,
                finalized_at=finalized_at,
            )
