"""調剤録代替の確認ユースケースのテスト。

主眼は3つ。

1. 認可と法人境界（他法人の薬歴・患者・処方箋は404相当に畳む）
2. 氏名を引けないスタッフを例外にせず、記載事項の未記載として返すこと
3. 氏名を問い合わせる対象が、調剤した薬剤師と指導した薬剤師に限られること

充足の判定そのものは Domain Service の責務なので、ここでは作り直さない。
"""

from __future__ import annotations

import pytest

from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryNotFoundError,
    MedicationHistoryPatientNotFoundError,
    MedicationHistoryPrescriptionNotFoundError,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.verify_statutory_record import (
    VerifyStatutoryRecordQuery,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    StatutoryDispensingRecordItem,
    StatutoryItemState,
    StatutoryRecordBlocker,
)
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_start_command,
)
from tests.factories.medication_history_factory import (
    create_independent_follow_up_record,
    create_nsips_draft_record,
    create_record,
    finalize_record_with_review,
)


async def _finalized_record_id(fixture: MedicationHistoryFixture) -> str:
    """既定の薬歴を1件起こして確定し、そのIDを返す。"""
    started = await fixture.start.execute(create_start_command(fixture))
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    return started.id


def _query(
    fixture: MedicationHistoryFixture, record_id: str
) -> VerifyStatutoryRecordQuery:
    """確認の入力を組み立てる。"""
    return VerifyStatutoryRecordQuery(
        corporate_id=str(fixture.corporate_id.value), record_id=record_id
    )


class Test調剤録代替の確認:
    """確定済の薬歴について、記載事項の充足を報告する。"""

    async def test_確定済の薬歴について_充足結果を返す(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)

        # Act
        result = await fixture.verify_statutory_record.execute(
            _query(fixture, record_id)
        )

        # Assert
        assert result.record_id == record_id
        assert len(result.assessments) == len(StatutoryDispensingRecordItem)
        assert result.blockers == ()
        assert result.substitutes_dispensing_record

    async def test_tc32_独立フォローアップは調剤録の代替判定対象にならない(
        self,
    ) -> None:
        fixture = create_fixture()
        initial = finalize_record_with_review(
            create_record(
                corporate_id=fixture.corporate_id,
                store_id=fixture.store_id,
                patient_id=fixture.patient_id,
                dispensing_id=fixture.dispensing.id,
                prescription_id=fixture.dispensing.prescription_id,
            )
        )
        follow_up = create_independent_follow_up_record(
            initial, store_id=fixture.store_id, finalized=True
        )
        await fixture.record_repository.save(follow_up)

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.verify_statutory_record.execute(
                _query(fixture, str(follow_up.id.value))
            )

    async def test_下書きの薬歴は_代替にならない理由が返る(self) -> None:
        """確認は確定済に限らない。足りないものを先に知るために使う。"""
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(create_start_command(fixture))

        # Act
        result = await fixture.verify_statutory_record.execute(
            _query(fixture, started.id)
        )

        # Assert
        assert not result.substitutes_dispensing_record
        assert StatutoryRecordBlocker.MEDICATION_HISTORY_NOT_FINALIZED.value in tuple(
            blocker.blocker for blocker in result.blockers
        )

    async def test_tc19_指導者未確定の下書きは_薬剤師氏名を未記載とする(self) -> None:
        fixture = create_fixture()
        record = create_nsips_draft_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
        )
        await fixture.record_repository.save(record)

        result = await fixture.verify_statutory_record.execute(
            _query(fixture, str(record.id.value))
        )

        counselor_assessment = next(
            assessment
            for assessment in result.assessments
            if assessment.item == "pharmacist_names"
        )
        assert counselor_assessment.state == StatutoryItemState.MISSING.value


class Test認可と法人境界:
    """他テナントは403ではなく404に畳む。"""

    async def test_無効な法人の薬歴は_確認できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        # Act / Assert
        with pytest.raises(CorporateInactiveError):
            await fixture.verify_statutory_record.execute(_query(fixture, record_id))

    async def test_他法人の薬歴は_見つからない扱いになる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.verify_statutory_record.execute(
                VerifyStatutoryRecordQuery(
                    corporate_id=str(CorporateId.generate().value),
                    record_id=record_id,
                )
            )

    async def test_存在しない薬歴は_見つからない扱いになる(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.verify_statutory_record.execute(
                _query(fixture, str(MedicationHistoryRecordId.generate().value))
            )


class Test参照境界の例外契約:
    """材料を集められないときに、何を例外へ畳み何を判定材料にするか。"""

    async def test_患者を解決できないと_見つからない扱いになる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)
        fixture.statutory_source.hide_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
        )

        # Act / Assert
        with pytest.raises(MedicationHistoryPatientNotFoundError):
            await fixture.verify_statutory_record.execute(_query(fixture, record_id))

    async def test_処方箋を解決できないと_見つからない扱いになる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)
        fixture.statutory_source.sources.clear()

        # Act / Assert
        with pytest.raises(MedicationHistoryPrescriptionNotFoundError):
            await fixture.verify_statutory_record.execute(_query(fixture, record_id))

    async def test_調剤セッションを解決できないと_見つからない扱いになる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)
        fixture.dispensing_source.processes.clear()

        # Act / Assert
        with pytest.raises(MedicationHistoryDispensingNotFoundError):
            await fixture.verify_statutory_record.execute(_query(fixture, record_id))

    async def test_氏名を引けないスタッフは_例外ではなく未記載になる(self) -> None:
        """記録に残ったスタッフの氏名を引けないこと自体が判定材料になる。

        取得の失敗として例外へ畳むと、「氏名を記載できない薬歴」を報告できない。
        """
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)
        fixture.statutory_source.resolvable = {fixture.dispensing.dispenser_id}

        # Act
        result = await fixture.verify_statutory_record.execute(
            _query(fixture, record_id)
        )

        # Assert
        states = {
            assessment.item: assessment.state for assessment in result.assessments
        }
        assert (
            states[StatutoryDispensingRecordItem.PHARMACIST_NAMES.value]
            == StatutoryItemState.MISSING.value
        )
        assert not result.substitutes_dispensing_record

    async def test_氏名を問い合わせるのは_調剤者と指導者だけ(self) -> None:
        """鑑査者まで巻き込むと、第五号が求めていない氏名を要求することになる。"""
        # Arrange
        fixture = create_fixture()
        record_id = await _finalized_record_id(fixture)

        # Act
        await fixture.verify_statutory_record.execute(_query(fixture, record_id))

        # Assert
        assert fixture.statutory_source.requested_staff_ids == [
            frozenset({fixture.dispensing.dispenser_id, fixture.counselor_id})
        ]
