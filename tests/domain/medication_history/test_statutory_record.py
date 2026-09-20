"""薬歴が調剤録の代替になるかの判定のテスト。

薬剤師法第28条は調剤録の作成を義務づけ、施行規則第16条第1項がその記載事項を
定める。記載事項は薬歴・調剤・処方箋・患者に分かれて存在するため、判定には
薬歴だけでなく調剤セッションと、処方箋・患者・薬剤師から取ったスナップショットが要る。

このテストは判定の条件式を再現しない。「どの入力を欠くと、どの記載事項が
未記載になるか」を独立に書く。期待値を実装から導くと、網羅していても実装と
同時にしか壊れない。
"""

from __future__ import annotations

from dataclasses import MISSING, fields, replace

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.foundation.exceptions import DomainError
from app.domain.medication_history import (
    SoapRecord,
    StatutoryDispensingRecordItem,
    StatutoryDispensingRecordService,
    StatutoryItemAssessment,
    StatutoryItemState,
    StatutoryRecordBlocker,
    StatutoryRecordSource,
    StatutoryRecordSourceMismatchError,
    StatutoryRecordSufficiency,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.services import STATUTORY_ITEM_RESOLVERS
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.staff.primitives import StaffId
from tests.factories.dispensing_factory import (
    GENERIC_CODE,
    GENERIC_NAME,
    cancel_dispensing,
    complete_dispensing,
    create_dispensed_medicine,
    create_dispensed_rp,
    create_dispensing,
    create_quantity_adjustment,
    create_substitution,
    verify_passed,
)
from tests.factories.medication_history_factory import (
    create_inquiry,
    create_note,
    create_pharmacist_name,
    create_record_for,
    create_statutory_source,
)

_ITEM = StatutoryDispensingRecordItem

type _Prepared = tuple[
    MedicationHistoryRecord, DispensingProcess, StatutoryRecordSource
]


def _prepared(
    *,
    dispensing: DispensingProcess | None = None,
    finalized: bool = True,
    soap: SoapRecord | None = None,
    patient_birth_date: object = "keep",
    institution_address: object = "keep",
    inquiries: tuple[object, ...] | None = None,
) -> _Prepared:
    """判定に渡す3点（薬歴・調剤・スナップショット）を組み立てる。

    既定は「記載事項が欠けていない交付済の調剤と確定済の薬歴」。ケースごとに
    欠けさせたいものだけを指定する。``"keep"`` はファクトリの既定を使う印。
    """
    process = (
        dispensing
        if dispensing is not None
        else complete_dispensing(create_dispensing())
    )
    record = create_record_for(process, soap=soap, finalized=finalized)
    overrides: dict[str, object] = {}
    if patient_birth_date != "keep":
        overrides["patient_birth_date"] = patient_birth_date
    if institution_address != "keep":
        overrides["institution_address"] = institution_address
    if inquiries is not None:
        overrides["inquiries"] = inquiries
    source = create_statutory_source(
        patient_id=record.patient_id,
        prescription_id=process.prescription_id,
        pharmacist_ids=(process.dispenser_id, record.counselor_id),
        **overrides,  # type: ignore[arg-type]
    )
    return record, process, source


def _verify(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryRecordSufficiency:
    """判定を実行する。"""
    return StatutoryDispensingRecordService().verify(record, dispensing, source)


def _diverged(dispensing: DispensingProcess, **overrides: object) -> DispensingProcess:
    """集約IDは同じまま、指定した属性だけ食い違う調剤セッションを作る。

    IDが一致していても法人・患者・処方箋が食い違えば判定できない、という点を
    確かめるための組み立て。
    """
    return replace(dispensing, **overrides)  # type: ignore[arg-type]


class Test法定記載事項の表:
    """記載事項の取りこぼしを、表と判定結果の両方で防ぐ。"""

    def test_判定表が_全ての号を覆う(self) -> None:
        """判定の無い記載事項があると、その号は黙って評価されない。"""
        # Act / Assert
        assert set(STATUTORY_ITEM_RESOLVERS) == set(StatutoryDispensingRecordItem)

    def test_号が欠けた判定結果は_構築できない(self) -> None:
        """記載事項を1つ落とした判定結果は、調剤録の充足を語れない。"""
        # Arrange
        assessments = tuple(
            StatutoryItemAssessment(item=item, state=StatutoryItemState.RECORDED)
            for item in StatutoryDispensingRecordItem
            if item is not _ITEM.PATIENT_NAME_AND_AGE
        )

        # Act / Assert
        with pytest.raises(DomainError):
            StatutoryRecordSufficiency(assessments=assessments, blockers=())

    def test_同じ号が重複した判定結果は_構築できない(self) -> None:
        """同じ記載事項に2つの状態が付くと、どちらが答えか決まらない。"""
        # Arrange
        assessments = (
            *(
                StatutoryItemAssessment(item=item, state=StatutoryItemState.RECORDED)
                for item in StatutoryDispensingRecordItem
            ),
            StatutoryItemAssessment(
                item=_ITEM.PATIENT_NAME_AND_AGE, state=StatutoryItemState.MISSING
            ),
        )

        # Act / Assert
        with pytest.raises(DomainError):
            StatutoryRecordSufficiency(assessments=assessments, blockers=())

    def test_全ての号に_日本語名と条文位置がある(self) -> None:
        """個別指導で示す先なので、号は条文の位置まで答えられる必要がある。"""
        # Act / Assert
        for item in StatutoryDispensingRecordItem:
            assert item.label
            assert item.article_clause

    def test_条文位置は_法令名まで含む(self) -> None:
        """応答本文に単独で現れても、どの法令の第何号かが特定できる必要がある。"""
        # Act / Assert
        for item in StatutoryDispensingRecordItem:
            assert item.article_clause.startswith("薬剤師法施行規則")

    def test_状態と阻害要因の全ての値に_日本語名がある(self) -> None:
        # Act / Assert
        for state in StatutoryItemState:
            assert state.label
        for blocker in StatutoryRecordBlocker:
            assert blocker.label

    def test_スナップショットは_既定値を持たない(self) -> None:
        """既定値があると、組み立て側の書き忘れが空の値として通る。

        空の値は「該当なし」と区別できないので、書き忘れは ``TypeError`` で
        落ちなければならない。
        """
        # Act
        defaulted = [
            field.name
            for field in fields(StatutoryRecordSource)
            if field.default is not MISSING or field.default_factory is not MISSING
        ]

        # Assert
        assert defaulted == []


class Test調剤録の代替:
    """記載事項がそろった基準形を固定する。"""

    def test_全ての記載事項がそろうと_調剤録の代替になる(self) -> None:
        # Arrange
        record, dispensing, source = _prepared()

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert sufficiency.blockers == ()
        assert sufficiency.missing_items == ()
        assert sufficiency.substitutes_dispensing_record

    def test_調剤と薬歴だけで充足する号は_スナップショットが欠けても変わらない(
        self,
    ) -> None:
        """薬名・分量、調剤日と指導日、調剤量は集約の不変条件が存在を保証する。

        スナップショットの任意項目を欠けさせても、これらの号は動かない。
        """
        # Arrange: 第一号と第九号が未記載になる欠けたスナップショット
        record, dispensing, source = _prepared(
            patient_birth_date=None, institution_address=None
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        for item in (
            _ITEM.MEDICINE_NAME_AND_AMOUNT,
            _ITEM.DISPENSED_AND_COUNSELED_DATE,
            _ITEM.DISPENSED_QUANTITY,
        ):
            assert sufficiency.state_of(item) is StatutoryItemState.RECORDED


class Test患者の氏名及び年齢:
    """第16条第1項第一号。"""

    def test_生年月日が無いと_年齢を記載できない(self) -> None:
        # Arrange
        record, dispensing, source = _prepared(patient_birth_date=None)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PATIENT_NAME_AND_AGE)
            is StatutoryItemState.MISSING
        )
        assert not sufficiency.substitutes_dispensing_record


class Test薬剤師の氏名:
    """第16条第1項第五号。調剤した薬剤師と指導した薬剤師の両方が要る。"""

    def test_調剤した薬剤師の氏名が引けないと_未記載になる(self) -> None:
        # Arrange
        dispensing = complete_dispensing(create_dispensing())
        record = create_record_for(dispensing)
        source = create_statutory_source(
            patient_id=record.patient_id,
            prescription_id=dispensing.prescription_id,
            pharmacist_ids=(record.counselor_id,),
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PHARMACIST_NAMES) is StatutoryItemState.MISSING
        )

    def test_指導した薬剤師の氏名が引けないと_未記載になる(self) -> None:
        # Arrange
        dispensing = complete_dispensing(create_dispensing())
        record = create_record_for(dispensing)
        source = create_statutory_source(
            patient_id=record.patient_id,
            prescription_id=dispensing.prescription_id,
            pharmacist_ids=(dispensing.dispenser_id,),
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PHARMACIST_NAMES) is StatutoryItemState.MISSING
        )

    def test_調剤者と指導者が同一人物でも_充足する(self) -> None:
        """一人薬剤師体制を拒まない。調剤側も別人であることは要求していない。"""
        # Arrange
        pharmacist_id = StaffId.generate()
        dispensing = complete_dispensing(create_dispensing(dispenser_id=pharmacist_id))
        record = create_record_for(dispensing, counselor_id=pharmacist_id)
        source = create_statutory_source(
            patient_id=record.patient_id,
            prescription_id=dispensing.prescription_id,
            pharmacist_ids=(pharmacist_id,),
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PHARMACIST_NAMES) is StatutoryItemState.RECORDED
        )

    def test_別人の氏名があっても_対象の薬剤師でなければ未記載(self) -> None:
        """件数ではなく、調剤者と指導者のIDで引けるかを判定する。"""
        # Arrange
        dispensing = complete_dispensing(create_dispensing())
        record = create_record_for(dispensing)
        source = create_statutory_source(
            patient_id=record.patient_id,
            prescription_id=dispensing.prescription_id,
            pharmacist_names=(
                create_pharmacist_name(StaffId.generate()),
                create_pharmacist_name(StaffId.generate()),
            ),
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PHARMACIST_NAMES) is StatutoryItemState.MISSING
        )


class Test医療機関の名称及び所在地:
    """第16条第1項第九号。"""

    def test_所在地が無いと_未記載になる(self) -> None:
        """処方箋の所在地は任意項目なので、実際に欠けうる。"""
        # Arrange
        record, dispensing, source = _prepared(institution_address=None)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.MEDICAL_INSTITUTION_LOCATION)
            is StatutoryItemState.MISSING
        )
        assert not sufficiency.substitutes_dispensing_record


class Test処方箋由来の記載事項:
    """第16条第1項第七号・第八号。"""

    def test_交付日と処方医氏名は_スナップショットから充足する(self) -> None:
        # Arrange
        record, dispensing, source = _prepared()

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.PRESCRIPTION_ISSUED_DATE)
            is StatutoryItemState.RECORDED
        )
        assert (
            sufficiency.state_of(_ITEM.PRESCRIBER_NAME) is StatutoryItemState.RECORDED
        )


class Test変更調剤と疑義照会:
    """第16条第1項第十号（施行規則第15条第一号・第二号）。3値すべてが起きる。"""

    def test_変更も照会も無ければ_該当なしになる(self) -> None:
        """起きていない事由を「未記載」に倒すと、正常な調剤が代替にならなくなる。"""
        # Arrange
        record, dispensing, source = _prepared()

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.NOT_REQUIRED
        )
        assert sufficiency.substitutes_dispensing_record

    def test_理由のある代替調剤は_記載済になる(self) -> None:
        # Arrange
        medicine = create_dispensed_medicine(
            code=GENERIC_CODE,
            name=GENERIC_NAME,
            substitution=create_substitution(
                reason="在庫が無く、同成分の後発品へ変更。"
            ),
        )
        dispensing = complete_dispensing(
            create_dispensing(
                dispensed_rps=(create_dispensed_rp(medicines=(medicine,)),)
            )
        )
        record, dispensing, source = _prepared(dispensing=dispensing)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.RECORDED
        )

    def test_理由の無い代替調剤は_変更の内容を再現できない(self) -> None:
        """代替調剤の理由は任意項目なので、変更の内容が残らない記録が作れる。"""
        # Arrange
        medicine = create_dispensed_medicine(
            code=GENERIC_CODE, name=GENERIC_NAME, substitution=create_substitution()
        )
        dispensing = complete_dispensing(
            create_dispensing(
                dispensed_rps=(create_dispensed_rp(medicines=(medicine,)),)
            )
        )
        record, dispensing, source = _prepared(dispensing=dispensing)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.MISSING
        )
        assert not sufficiency.substitutes_dispensing_record

    def test_減数調剤は_理由が必須なので記載済になる(self) -> None:
        # Arrange
        dispensing = complete_dispensing(
            create_dispensing(
                dispensed_rps=(
                    create_dispensed_rp(
                        quantity_adjustment=create_quantity_adjustment()
                    ),
                )
            )
        )
        record, dispensing, source = _prepared(dispensing=dispensing)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.RECORDED
        )

    def test_回答済の疑義照会は_記載済になる(self) -> None:
        # Arrange
        record, dispensing, source = _prepared(
            inquiries=(create_inquiry(has_response=True),)
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.RECORDED
        )

    def test_未回答の疑義照会が残ると_回答内容を記載できない(self) -> None:
        # Arrange
        record, dispensing, source = _prepared(
            inquiries=(create_inquiry(has_response=False),)
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.MISSING
        )

    def test_未回答が1件でも混ざれば_未記載になる(self) -> None:
        """「どれか1件でも回答済なら充足」という判定を通さない。"""
        # Arrange
        record, dispensing, source = _prepared(
            inquiries=(
                create_inquiry(1, has_response=True),
                create_inquiry(2, has_response=False),
            )
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.CHANGE_AND_INQUIRY_DETAIL)
            is StatutoryItemState.MISSING
        )


class Test調剤録の代替を妨げる要因:
    """記載事項とは別軸。書き換えられる記録や、交付していない調剤は代替にならない。"""

    def test_下書きの薬歴は_記載がそろっていても代替にならない(self) -> None:
        """確定していない記録はいつでも書き換えられる。"""
        # Arrange
        record, dispensing, source = _prepared(finalized=False)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            StatutoryRecordBlocker.MEDICATION_HISTORY_NOT_FINALIZED
            in sufficiency.blockers
        )
        assert not sufficiency.substitutes_dispensing_record
        # 阻害要因で打ち切らず、記載事項の判定も返す。
        assert len(sufficiency.assessments) == len(StatutoryDispensingRecordItem)

    def test_記載の無いSOAPセクションがあると_指導の要点が未記載になる(self) -> None:
        """確定済にはできない組み合わせなので、下書きで確かめる。"""
        # Arrange
        soap = SoapRecord(
            subjective=(create_note(),),
            objective=(create_note(),),
            assessment=(create_note(),),
            plan=(),
        )
        record, dispensing, source = _prepared(finalized=False, soap=soap)

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert (
            sufficiency.state_of(_ITEM.COUNSELING_SUMMARY) is StatutoryItemState.MISSING
        )

    def test_交付前の調剤は_調剤録の代替にならない(self) -> None:
        # Arrange
        record, dispensing, source = _prepared(
            dispensing=verify_passed(create_dispensing())
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert StatutoryRecordBlocker.DISPENSING_NOT_COMPLETED in sufficiency.blockers
        assert not sufficiency.substitutes_dispensing_record

    def test_中止した調剤は_調剤録の代替にならない(self) -> None:
        # Arrange
        record, dispensing, source = _prepared(
            dispensing=cancel_dispensing(create_dispensing())
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert StatutoryRecordBlocker.DISPENSING_NOT_COMPLETED in sufficiency.blockers
        assert not sufficiency.substitutes_dispensing_record

    def test_阻害要因は_該当するものが全て並ぶ(self) -> None:
        """片方を見つけた時点で打ち切ると、直すべき点が1つずつしか見えない。"""
        # Arrange
        record, dispensing, source = _prepared(
            dispensing=verify_passed(create_dispensing()), finalized=False
        )

        # Act
        sufficiency = _verify(record, dispensing, source)

        # Assert
        assert set(sufficiency.blockers) == {
            StatutoryRecordBlocker.MEDICATION_HISTORY_NOT_FINALIZED,
            StatutoryRecordBlocker.DISPENSING_NOT_COMPLETED,
        }
        assert len(sufficiency.blockers) == 2


class Test取り違えの拒否:
    """無関係な記録を継ぎ接ぎした「充足」を作らせない。"""

    def test_別の調剤セッションを渡すと_拒否される(self) -> None:
        # Arrange
        record, _, source = _prepared()
        other = complete_dispensing(create_dispensing())

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(record, other, source)

    def test_法人が違う調剤セッションは_拒否される(self) -> None:
        # Arrange
        record, dispensing, source = _prepared()

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(
                record,
                _diverged(dispensing, corporate_id=CorporateId.generate()),
                source,
            )

    def test_患者が違う調剤セッションは_拒否される(self) -> None:
        # Arrange
        record, dispensing, source = _prepared()

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(
                record, _diverged(dispensing, patient_id=PatientId.generate()), source
            )

    def test_処方箋が違う調剤セッションは_拒否される(self) -> None:
        # Arrange
        record, dispensing, source = _prepared()

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(
                record,
                _diverged(dispensing, prescription_id=PrescriptionId.generate()),
                source,
            )

    def test_別の患者から作ったスナップショットは_拒否される(self) -> None:
        """患者の氏名と年齢はスナップショットだけから判定される。

        取り違えを通すと、別人の氏名を根拠に第一号が充足したと報告することになる。
        """
        # Arrange
        record, dispensing, _ = _prepared()
        other_patient_source = create_statutory_source(
            patient_id=PatientId.generate(),
            prescription_id=dispensing.prescription_id,
            pharmacist_ids=(dispensing.dispenser_id, record.counselor_id),
        )

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(record, dispensing, other_patient_source)

    def test_別の処方箋から作ったスナップショットは_拒否される(self) -> None:
        # Arrange
        record, dispensing, _ = _prepared()
        other_source = create_statutory_source(
            patient_id=record.patient_id,
            prescription_id=PrescriptionId.generate(),
            pharmacist_ids=(dispensing.dispenser_id, record.counselor_id),
        )

        # Act / Assert
        with pytest.raises(StatutoryRecordSourceMismatchError):
            _verify(record, dispensing, other_source)
