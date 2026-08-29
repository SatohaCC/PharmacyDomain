"""薬歴指導記録集約のテスト。

法定記載事項（保険調剤の理解のために 令和8年度 第2節 通則(4)）のうち、
集約が単独で判定できるものを固定する。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.medication_history import (
    AmendmentReason,
    AmendmentTimestamp,
    HandbookConsolidationReason,
    HandbookGuidanceRequiredError,
    HandbookNotPresentedReason,
    HandbookReasonNotAllowedError,
    HandbookStatus,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryStatus,
    ResidualDrugDetailNotAllowedError,
    ResidualDrugDetailRequiredError,
    ResidualDrugQuantity,
    ResidualDrugReason,
    ResidualDrugRecord,
    SoapRecord,
    SoapSectionEmptyError,
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
    """不変条件 #3。法定記載事項ウ（ホ）。"""

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
    """不変条件 #4。法定記載事項ウ（ト）。"""

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
    """不変条件 #2 / #7。"""

    def test_下書きでは_SOAPが空でも構築できる(self) -> None:
        """聞き取りながら書き足す運用を壊さない。"""
        # Arrange / Act
        actual = create_record(soap=SoapRecord())

        # Assert
        assert actual.status is MedicationHistoryStatus.DRAFT

    @pytest.mark.parametrize(
        ("section", "label"),
        [
            ("subjective", "S（主観的情報）"),
            ("objective", "O（客観的情報）"),
            ("assessment", "A（評価）"),
            ("plan", "P（計画）"),
        ],
    )
    def test_SOAPのいずれかが空だと_確定できない(
        self, section: str, label: str
    ) -> None:
        # Arrange
        soap = create_soap()
        empty_soap = type(soap)(
            **{
                **{
                    name: getattr(soap, name)
                    for name in ("subjective", "objective", "assessment", "plan")
                },
                section: (),
            }
        )
        record = create_record(soap=empty_soap)

        # Act / Assert
        with pytest.raises(SoapSectionEmptyError, match=label):
            record.finalize()

    def test_空文字だけの記載は_記載とみなさない(self) -> None:
        """定型文の空欄を埋めただけの記録を確定させない。"""
        # Arrange
        soap = create_soap()
        record = create_record(
            soap=type(soap)(
                subjective=(create_note("   "),),
                objective=soap.objective,
                assessment=soap.assessment,
                plan=soap.plan,
            )
        )

        # Act / Assert
        with pytest.raises(SoapSectionEmptyError):
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
