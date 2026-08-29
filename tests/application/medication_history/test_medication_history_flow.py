"""薬歴ユースケースのテスト。

主眼は3つ。

1. 認可と法人境界（他法人の店舗・調剤・スタッフは404相当に畳む）
2. 保存順序が ``save(record)`` → ``save(profile)`` であること
3. 頭書きの保存に失敗しても、薬歴から再構築して回復できること
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history import (
    AllergyIntentInput,
    AmendMedicationHistoryCommand,
    ConcurrentMedicationIntentInput,
    FinalizeMedicationHistoryCommand,
    GetMedicationHistoryQuery,
    GetPatientMedicalProfileQuery,
    ListMedicationHistoriesQuery,
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
    PatientMedicalProfileNotFoundError,
    ProfileUpdateInput,
    RebuildPatientMedicalProfileCommand,
    SoapInput,
    StopConcurrentMedicationIntentInput,
    UpdateMedicationHistoryDraftCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    CounselorQualificationError,
    MedicationHistoryAlreadyExistsError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryStatus,
    SoapSectionEmptyError,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_soap_input,
    create_start_command,
    register_another_dispensing,
)

_AS_OF = date(2026, 8, 24)
_STARTED_ON = date(2026, 8, 1)


def _allergy_updates() -> ProfileUpdateInput:
    """アレルギー歴を1件追加する差分の入力。"""
    return ProfileUpdateInput(
        new_allergies=(
            AllergyIntentInput(
                allergen="ペニシリン系", reaction="皮疹", severity="moderate"
            ),
        )
    )


async def _start(fixture: MedicationHistoryFixture) -> str:
    """既定の薬歴を1件起こし、そのIDを返す。"""
    started = await fixture.start.execute(create_start_command(fixture))
    return started.id


async def _finalize(fixture: MedicationHistoryFixture, record_id: str) -> None:
    """薬歴を確定する。"""
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value), record_id=record_id
        )
    )


class Test薬歴の作成:
    """調剤との一致と指導者の資格を確認して起こす。"""

    async def test_薬歴を起こすと_下書きで保存される(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.status == MedicationHistoryStatus.DRAFT.value
        assert actual.patient_id == str(fixture.patient_id.value)
        assert actual.prescription_id == str(fixture.dispensing.prescription_id.value)

    async def test_患者は調剤セッションから決まる(self) -> None:
        """Commandに患者IDを持たせない。調剤と食い違う患者の薬歴を作れてしまう。"""
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture)

        # Act
        actual = await fixture.start.execute(command)

        # Assert
        assert not hasattr(command, "patient_id")
        assert actual.patient_id == str(fixture.dispensing.patient_id.value)

    async def test_指導日時は_Commandではなく注入Clockから来る(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.clock.advance(timedelta(hours=5))

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.counseled_at.startswith("2026-08-23T08:00")

    async def test_残薬なしを_明示的に記録できる(self) -> None:
        """法定記載事項ウ（ホ）「残薬がないときは、その旨を記載すること」。"""
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.residual_drug.has_residual_drugs is False

    async def test_下書きは_SOAPが空でも作れる(self) -> None:
        """聞き取りながら書き足す運用を壊さない。"""
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(
            create_start_command(fixture, soap=SoapInput())
        )

        # Assert
        assert actual.status == MedicationHistoryStatus.DRAFT.value


class Test認可と法人境界:
    """他テナントは403ではなく404に畳む。"""

    async def test_無効な法人では_作成できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        # Act / Assert
        with pytest.raises(CorporateInactiveError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_別法人の店舗を指定すると_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.store_reference.registered.clear()

        # Act / Assert
        with pytest.raises(MedicationHistoryStoreNotFoundError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_別法人の調剤を指定すると_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.dispensing_source.processes.clear()

        # Act / Assert
        with pytest.raises(MedicationHistoryDispensingNotFoundError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_在籍していないスタッフは_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture, counselor_id=StaffId.generate())

        # Act / Assert
        with pytest.raises(MedicationHistoryStaffNotFoundError):
            await fixture.start.execute(command)

    async def test_他法人からは_薬歴を取得できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.get.execute(
                GetMedicationHistoryQuery(
                    corporate_id=str(CorporateId.generate().value),
                    record_id=record_id,
                )
            )


class Test服薬指導者の資格:
    """薬剤師法第25条の2に基づく指導者の資格を検証する。"""

    async def test_薬剤師資格が無いと_薬歴を起こせない(self) -> None:
        # Arrange
        fixture = create_fixture()
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        # Act / Assert
        with pytest.raises(CounselorQualificationError):
            await fixture.start.execute(
                create_start_command(fixture, counselor_id=clerk_id)
            )

    async def test_薬剤師資格が無いと_追記できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        await _finalize(fixture, record_id)
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        # Act / Assert
        with pytest.raises(CounselorQualificationError):
            await fixture.amend.execute(
                AmendMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=record_id,
                    amended_by=str(clerk_id.value),
                    reason="記載漏れがあったため。",
                    amended_soap=create_soap_input(),
                )
            )


class Test確定と投影:
    """保存順序と頭書きへの反映。"""

    async def test_確定すると_頭書きへ差分が投影される(self) -> None:
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )

        # Act
        actual = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value), record_id=started.id
            )
        )

        # Assert
        assert actual.status == MedicationHistoryStatus.FINALIZED.value
        profile = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )
        assert len(profile.allergies) == 1
        assert profile.allergies[0].provenance.source_record_id == started.id

    async def test_SOAPが空だと_確定できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, soap=SoapInput())
        )

        # Act / Assert
        with pytest.raises(SoapSectionEmptyError):
            await _finalize(fixture, started.id)

    async def test_確定済は_下書きを編集できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        await _finalize(fixture, record_id)

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            await fixture.update_draft.execute(
                UpdateMedicationHistoryDraftCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=record_id,
                    soap=create_soap_input(subjective="書き換えたい内容。"),
                )
            )

    async def test_同一調剤に_確定済を2件作れない(self) -> None:
        # Arrange
        fixture = create_fixture()
        first = await _start(fixture)
        second = await _start(fixture)
        await _finalize(fixture, first)

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyExistsError):
            await _finalize(fixture, second)

    async def test_頭書きの保存が失敗しても_薬歴は残る(self) -> None:
        """保存順序 ``save(record)`` → ``save(profile)`` を固定する。

        逆順にすると、根拠のない頭書きだけが残って由来を追えなくなる。
        """
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )
        fixture.profile_repository.fail_next_save_for(fixture.patient_id)

        # Act
        with pytest.raises(RuntimeError, match="頭書きの保存に失敗"):
            await _finalize(fixture, started.id)

        # Assert: 薬歴は確定済で残り、頭書きは作られていない
        stored = await fixture.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=str(fixture.corporate_id.value), record_id=started.id
            )
        )
        assert stored.status == MedicationHistoryStatus.FINALIZED.value
        with pytest.raises(PatientMedicalProfileNotFoundError):
            await fixture.get_profile.execute(
                GetPatientMedicalProfileQuery(
                    corporate_id=str(fixture.corporate_id.value),
                    patient_id=str(fixture.patient_id.value),
                    as_of=_AS_OF,
                )
            )

    async def test_頭書きの保存に失敗しても_薬歴から再構築して回復できる(self) -> None:
        """投影であることが、原子性の代わりに整合性を回復可能にしている。"""
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )
        fixture.profile_repository.fail_next_save_for(fixture.patient_id)
        with pytest.raises(RuntimeError):
            await _finalize(fixture, started.id)
        fixture.profile_repository.failing_patient_ids.clear()

        # Act
        actual = await fixture.rebuild_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Assert
        assert len(actual.allergies) == 1
        assert actual.allergies[0].provenance.source_record_id == started.id

    async def test_再構築は_未確定の薬歴を取り込まない(self) -> None:
        """下書きは以降も書き換わるため、投影の入力にすると結果が安定しない。"""
        # Arrange
        fixture = create_fixture()
        await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )

        # Act
        actual = await fixture.rebuild_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Assert
        assert actual.allergies == ()

    async def test_再構築しても_頭書きの同一性は変わらない(self) -> None:
        """新しいIDで作り直すと、患者ごと1件の一意制約に引っかかる。"""
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )
        await _finalize(fixture, started.id)
        before = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Act
        after = await fixture.rebuild_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Assert
        assert after.id == before.id
        assert len(after.allergies) == 1


class Test追記:
    """確定済の修正は追記のみ。"""

    async def test_未確定には_追記できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(MedicationHistoryNotFinalizedError):
            await fixture.amend.execute(
                AmendMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=record_id,
                    amended_by=str(fixture.counselor_id.value),
                    reason="記載漏れがあったため。",
                    amended_soap=create_soap_input(),
                )
            )

    async def test_追記しても_元のSOAPは書き換わらない(self) -> None:
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(
                fixture, soap=create_soap_input(subjective="交付時の記載。")
            )
        )
        await _finalize(fixture, started.id)

        # Act
        actual = await fixture.amend.execute(
            AmendMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                amended_by=str(fixture.counselor_id.value),
                reason="記載漏れがあったため。",
                amended_soap=create_soap_input(subjective="追記後の記載。"),
            )
        )

        # Assert
        assert actual.soap.subjective[0].text == "交付時の記載。"
        assert actual.effective_soap.subjective[0].text == "追記後の記載。"
        assert len(actual.amendments) == 1

    async def test_追記しても_頭書きは動かない(self) -> None:
        """頭書きへの差分は確定時に固定される。追記で動かすと再構築と食い違う。"""
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )
        await _finalize(fixture, started.id)

        # Act
        await fixture.amend.execute(
            AmendMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                amended_by=str(fixture.counselor_id.value),
                reason="記載漏れがあったため。",
                amended_soap=create_soap_input(subjective="追記後の記載。"),
            )
        )

        # Assert
        profile = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )
        assert len(profile.allergies) == 1


class Test頭書きの参照:
    """併用薬の判定は適用日で決まる。"""

    async def test_併用薬は_適用日ごとに継続中かが決まる(self) -> None:
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(
                fixture,
                profile_updates=ProfileUpdateInput(
                    new_concurrent_medications=(
                        ConcurrentMedicationIntentInput(
                            medicine_name="市販の総合感冒薬",
                            category="otc",
                            started_on=_STARTED_ON,
                        ),
                    )
                ),
            )
        )
        await _finalize(fixture, started.id)

        # Act
        before = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=date(2026, 7, 31),
            )
        )
        after = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Assert
        assert before.active_concurrent_medications == ()
        assert len(after.active_concurrent_medications) == 1
        assert len(before.concurrent_medications) == 1

    async def test_併用薬の終了も_薬歴から投影される(self) -> None:
        # Arrange
        fixture = create_fixture()
        first = await fixture.start.execute(
            create_start_command(
                fixture,
                profile_updates=ProfileUpdateInput(
                    new_concurrent_medications=(
                        ConcurrentMedicationIntentInput(
                            medicine_name="市販の総合感冒薬",
                            category="otc",
                            started_on=_STARTED_ON,
                        ),
                    )
                ),
            )
        )
        await _finalize(fixture, first.id)
        another = register_another_dispensing(fixture)
        second = await fixture.start.execute(
            create_start_command(
                fixture,
                dispensing=another,
                profile_updates=ProfileUpdateInput(
                    stopped_concurrent_medications=(
                        StopConcurrentMedicationIntentInput(
                            medicine_name="市販の総合感冒薬",
                            ended_on=date(2026, 8, 20),
                        ),
                    )
                ),
            )
        )
        await _finalize(fixture, second.id)

        # Act
        actual = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        # Assert
        assert actual.concurrent_medications[0].ended_on == "2026-08-20"
        assert actual.active_concurrent_medications == ()

    async def test_未投影の患者は_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act / Assert
        with pytest.raises(PatientMedicalProfileNotFoundError):
            await fixture.get_profile.execute(
                GetPatientMedicalProfileQuery(
                    corporate_id=str(fixture.corporate_id.value),
                    patient_id=str(fixture.patient_id.value),
                    as_of=_AS_OF,
                )
            )


class Test一覧:
    """タイムラインは新しい順。"""

    async def test_服薬指導日時の降順で返る(self) -> None:
        # Arrange
        fixture = create_fixture()
        await _start(fixture)
        fixture.clock.advance(timedelta(days=7))
        another = register_another_dispensing(fixture)
        await fixture.start.execute(create_start_command(fixture, dispensing=another))

        # Act
        actual = await fixture.list_by_patient.execute(
            ListMedicationHistoriesQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
            )
        )

        # Assert
        assert len(actual) == 2
        assert actual[0].counseled_at > actual[1].counseled_at

    async def test_他法人からは_一覧に現れない(self) -> None:
        # Arrange
        fixture = create_fixture()
        await _start(fixture)

        # Act
        actual = await fixture.list_by_patient.execute(
            ListMedicationHistoriesQuery(
                corporate_id=str(CorporateId.generate().value),
                patient_id=str(fixture.patient_id.value),
            )
        )

        # Assert
        assert actual == ()
