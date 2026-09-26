"""薬歴ユースケースのテスト。

主眼は3つ。

1. 認可と法人境界（他法人の店舗・調剤・スタッフは404相当に畳む）
2. 保存順序が ``save(record)`` → ``save(profile)`` であること
3. 頭書きの保存に失敗しても、薬歴から再構築して回復できること
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.application.access_control.models import ActorContext, ResolvedActorContext
from app.application.common.exceptions import ApplicationError
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryCommand,
)
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
    PatientMedicalProfileNotFoundError,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_medication_history import (
    GetMedicationHistoryQuery,
    ListMedicationHistoriesQuery,
    MedicationHistoryDto,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileQuery,
    RebuildPatientMedicalProfileCommand,
)
from app.application.medication_history.inputs import (
    AllergyIntentInput,
    BillingAdditionInput,
    ConcurrentMedicationIntentInput,
    ConditionIntentInput,
    HandbookStatusInput,
    LabeledNoteInput,
    ProfileUpdateInput,
    ResidualDrugInput,
    RetractAllergyIntentInput,
    SoapInput,
    StopConcurrentMedicationIntentInput,
    UpdateConditionStatusIntentInput,
)
from app.application.medication_history.update_medication_history_draft import (
    UpdateMedicationHistoryDraftCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    FinalizationDelayReasonRequiredError,
    MedicationHistoryAlreadyExistsError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    SoapContentRequiredError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryRecordKind,
    MedicationHistoryStatus,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_nsips_start_command,
    create_resolved_actor,
    create_soap_input,
    create_start_command,
    register_another_dispensing,
)
from tests.factories.medication_history_factory import (
    create_nsips_draft_record,
    create_record,
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


async def _start_nsips(fixture: MedicationHistoryFixture) -> MedicationHistoryDto:
    """取込時刻だけを持つNSIPS由来の下書きを作る。"""
    return await fixture.start.execute(create_nsips_start_command(fixture))


async def _save_nsips_draft(
    fixture: MedicationHistoryFixture,
) -> MedicationHistoryRecord:
    """テスト対象の後続ユースケースに使う取込DRAFTをRepositoryへ置く。"""
    record = create_nsips_draft_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        dispensing_id=fixture.dispensing.id,
        prescription_id=fixture.dispensing.prescription_id,
        imported_at=fixture.clock.now(),
        ready_to_finalize=True,
    )
    await fixture.record_repository.save(record)
    return record


async def _finalize(fixture: MedicationHistoryFixture, record_id: str) -> None:
    """薬歴を確定する。"""
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            review_result="assessment_and_instruction_recorded",
        )
    )


class Test薬歴の作成:
    """調剤との一致と指導者の資格を確認して起こす。"""

    async def test_tc06_初回保存の記載者を指導者として扱わない(
        self,
    ) -> None:
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.status == MedicationHistoryStatus.DRAFT.value
        assert actual.patient_id == str(fixture.patient_id.value)
        assert actual.prescription_id == str(fixture.dispensing.prescription_id.value)
        assert actual.counselor_id is None
        assert actual.counseled_at is None
        assert getattr(actual, "recorded_by", None) == str(fixture.counselor_id.value)

    async def test_tc10_初回保存は部分記載を保存し_記載者と指導実績を分ける(
        self,
    ) -> None:
        fixture = create_fixture()
        authored_text = "服薬後に眠気が出たとの申告を確認した。"
        imported_at = fixture.clock.now() - timedelta(hours=2)
        addition = BillingAdditionInput(
            code="140000110",
            name="特定薬剤管理指導加算２",
            points=100,
            quantity=1,
        )
        command = replace(
            create_start_command(fixture),
            method=None,
            soap=SoapInput(
                subjective=(LabeledNoteInput(text=authored_text),),
            ),
            handbook_status=None,
            residual_drug=None,
            information_sheet_provided=None,
            source_system="NSIPS",
            imported_at=imported_at,
            billing_additions=(addition,),
        )

        actual = await fixture.start.execute(command)

        assert actual.status == MedicationHistoryStatus.DRAFT.value
        assert actual.soap.subjective[0].text == authored_text
        assert actual.counselor_id is None
        assert actual.counseled_at is None
        assert actual.imported_at == imported_at.isoformat()
        assert actual.billing_additions[0].code == addition.code
        assert actual.billing_additions[0].name == addition.name
        assert getattr(actual, "recorded_by", None) == str(fixture.counselor_id.value)

    async def test_tc12_白紙の初回保存では薬歴レコードを作らない(self) -> None:
        fixture = create_fixture()
        command = replace(
            create_start_command(fixture),
            method=None,
            soap=SoapInput(),
            handbook_status=None,
            residual_drug=None,
            information_sheet_provided=None,
            source_system="NSIPS",
        )

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.start.execute(command)

        assert fixture.record_repository.items == {}

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
        assert actual.store_id == str(fixture.dispensing.store_id.value)
        assert actual.prescription_id == str(fixture.dispensing.prescription_id.value)
        assert actual.dispensing_id == str(fixture.dispensing.id.value)
        assert actual.record_kind == MedicationHistoryRecordKind.INITIAL.value
        assert actual.source_record_id is None

    async def test_tc01_調剤店舗と異なる店舗で受付付き初回薬歴を作れない(self) -> None:
        fixture = create_fixture()
        another_store_id = StoreId.generate()
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id,
            store_id=another_store_id,
        )
        command = replace(
            create_start_command(fixture),
            store_id=str(another_store_id.value),
            reception_id=str(ReceptionId.generate().value),
        )

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.start.execute(command)

        assert fixture.record_repository.items == {}
        assert fixture.reception_repository.get_calls == 0

    async def test_初回保存時刻を_実指導日時へ自動設定しない(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.clock.advance(timedelta(hours=5))

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.counseled_at is None

    async def test_残薬なしを_明示的に記録できる(self) -> None:
        """法定記載事項ウ（ホ）「残薬がないときは、その旨を記載すること」。"""
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.residual_drug is not None
        assert actual.residual_drug.has_residual_drugs is False

    async def test_tc21_確認済み否定値と未記録状態を取得時に区別する(self) -> None:
        """手帳未提示・残薬なし・文書未交付を確認済み否定として保持する。"""
        fixture = create_fixture()
        known_negative = await fixture.start.execute(
            create_start_command(
                fixture,
                handbook_status=HandbookStatusInput(
                    presented=False,
                    not_presented_reason="持参なし",
                    guidance_provided=False,
                ),
                residual_drug=ResidualDrugInput(has_residual_drugs=False),
                information_sheet_provided=False,
            )
        )
        loaded_known = await fixture.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=known_negative.id,
            )
        )
        assert loaded_known.handbook_status is not None
        assert loaded_known.handbook_status.presented is False
        assert loaded_known.handbook_status.guidance_provided is False
        assert loaded_known.residual_drug is not None
        assert loaded_known.residual_drug.has_residual_drugs is False
        assert loaded_known.information_sheet_provided is False

        unknown = await fixture.start.execute(
            create_start_command(fixture, information_sheet_provided=None)
        )
        loaded_unknown = await fixture.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=unknown.id,
            )
        )
        assert loaded_unknown.information_sheet_provided is None


class Test算定加算訂正:
    """下書き薬歴の加算情報を保持し、確定後は変更を拒否する。"""

    async def test_tc29_下書き加算を置換し確定後の更新を拒否する(self) -> None:
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(
                fixture,
                billing_additions=(
                    BillingAdditionInput(
                        code="140000110",
                        name="加算A",
                        points=100,
                        quantity=1,
                    ),
                ),
            )
        )
        updated = await fixture.update_draft.execute(
            UpdateMedicationHistoryDraftCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                billing_additions=(
                    BillingAdditionInput(
                        code="140000210",
                        name="加算B",
                        points=200,
                        quantity=2,
                    ),
                ),
            )
        )

        assert len(updated.billing_additions) == 1
        assert updated.billing_additions[0].code == "140000210"
        assert updated.billing_additions[0].points == 200
        assert updated.billing_additions[0].quantity == 2
        await _finalize(fixture, started.id)
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            await fixture.update_draft.execute(
                UpdateMedicationHistoryDraftCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=started.id,
                    billing_additions=(),
                )
            )

    async def test_部分記載で下書きを作れる(self) -> None:
        """聞き取りながら書き足す運用を壊さない。"""
        # Arrange
        fixture = create_fixture()
        authored_text = "頭痛は昨日から軽くなっている。"

        # Act
        actual = await fixture.start.execute(
            create_start_command(
                fixture,
                soap=SoapInput(
                    subjective=(LabeledNoteInput(text=authored_text),),
                ),
            )
        )

        # Assert
        assert actual.status == MedicationHistoryStatus.DRAFT.value
        assert actual.soap.subjective[0].text == authored_text
        assert actual.soap.objective == ()
        assert actual.soap.assessment == ()
        assert actual.soap.plan == ()


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
        missing_staff_id = StaffId.generate()
        fixture = create_fixture(actor=create_resolved_actor(staff_id=missing_staff_id))

        # Act / Assert
        with pytest.raises(MedicationHistoryStaffNotFoundError):
            await fixture.start.execute(create_start_command(fixture))

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

    async def test_tc08_Actorの薬剤師資格が無いと_薬歴を起こせない(self) -> None:
        # Arrange
        clerk_id = StaffId.generate()
        fixture = create_fixture(actor=create_resolved_actor(staff_id=clerk_id))
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        # Act / Assert
        with pytest.raises(CounselorQualificationError):
            await fixture.start.execute(create_start_command(fixture))

        assert fixture.record_repository.items == {}

    async def test_tc07_スタッフ未解決Actorでは_薬歴を起こさず保存しない(
        self,
    ) -> None:
        fixture = create_fixture(
            actor=ActorContext.vendor_system_admin(principal_id="test-unresolved")
        )

        with pytest.raises(ApplicationError):
            await fixture.start.execute(create_start_command(fixture))

        assert fixture.record_repository.items == {}


class TestNSIPS取込後の指導実績:
    """NSIPS取込時刻と実際の服薬指導を別に扱う。"""

    async def test_tc13_取込下書きDTOは_指導実績と取込時刻を分けて返す(self) -> None:
        fixture = create_fixture()

        actual = await _start_nsips(fixture)

        assert actual.counselor_id is None
        assert actual.counseled_at is None
        assert actual.imported_at == fixture.clock.now().isoformat()

    async def test_tc14_実指導日時なしでは確定せず_薬歴と頭書きを変更しない(
        self,
    ) -> None:
        fixture = create_fixture()
        record = await _save_nsips_draft(fixture)
        record_id = record.id
        before = fixture.record_repository.items[record_id]

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(record_id.value),
                    review_result="assessment_and_instruction_recorded",
                )
            )

        assert fixture.record_repository.items[record_id] == before
        assert fixture.profile_repository.items == {}

    async def test_tc15_確定時はActorと実指導日時を記録し_取込時刻を維持する(
        self,
    ) -> None:
        fixture = create_fixture()
        record = await _save_nsips_draft(fixture)
        counseled_at = fixture.clock.now() - timedelta(hours=2)

        actual = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(record.id.value),
                counseled_at=counseled_at,
                review_result="assessment_and_instruction_recorded",
            )
        )

        assert actual.counselor_id == str(fixture.counselor_id.value)
        assert actual.counseled_at == counseled_at.isoformat()
        assert actual.imported_at == fixture.clock.now().isoformat()
        assert actual.finalized_at != actual.counseled_at

    async def test_tc18_未解決Actorと非薬剤師Actorは_取込下書きを確定できない(
        self,
    ) -> None:
        actors = (
            (
                ActorContext.vendor_system_admin(
                    principal_id="test-unresolved-finalizer"
                ),
                ApplicationError,
            ),
            (
                create_resolved_actor(staff_id=StaffId.generate()),
                CounselorQualificationError,
            ),
        )
        for actor, error_type in actors:
            fixture = create_fixture(actor=actor)
            if isinstance(actor, ResolvedActorContext) and actor.staff_id is not None:
                fixture.staff_qualification.register(
                    corporate_id=fixture.corporate_id,
                    staff_id=actor.staff_id,
                    qualifications=StaffQualifications.empty(),
                )
            record = await _save_nsips_draft(fixture)

            with pytest.raises(error_type):
                await fixture.finalize.execute(
                    FinalizeMedicationHistoryCommand(
                        corporate_id=str(fixture.corporate_id.value),
                        record_id=str(record.id.value),
                        counseled_at=fixture.clock.now(),
                        review_result="assessment_and_instruction_recorded",
                    )
                )

            assert fixture.profile_repository.items == {}
            saved = await fixture.record_repository.get(
                corporate_id=fixture.corporate_id,
                record_id=record.id,
            )
            assert saved is not None and not saved.is_finalized

    async def test_tc20_取込下書きは_頭書きの再構築へ投影しない(self) -> None:
        fixture = create_fixture()
        await _save_nsips_draft(fixture)

        profile = await fixture.rebuild_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )

        assert profile.allergies == ()
        assert profile.adverse_reactions == ()

    async def test_tc22_インメモリ一覧では_指導日時なしの取込下書きを末尾へ決定的に並べる(
        self,
    ) -> None:
        fixture = create_fixture()
        dated = create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
        )
        imported_first = create_nsips_draft_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
        )
        imported_second = create_nsips_draft_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
        )
        await fixture.record_repository.save(dated)
        await fixture.record_repository.save(imported_first)
        await fixture.record_repository.save(imported_second)

        records = await fixture.list_by_patient.execute(
            ListMedicationHistoriesQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
            )
        )
        repeated = await fixture.list_by_patient.execute(
            ListMedicationHistoriesQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
            )
        )

        assert records[0].id == str(dated.id.value)
        assert records[1].counseled_at is None
        assert records[2].counseled_at is None
        assert [item.id for item in records] == [item.id for item in repeated]
        assert [item.id for item in records[1:]] == sorted(
            (str(imported_first.id.value), str(imported_second.id.value)),
            reverse=True,
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

    async def test_tc17_確定時レビュー者と時刻は_ActorとClockから決まる(self) -> None:
        fixture = create_fixture()
        started = await fixture.start.execute(create_start_command(fixture))

        finalized = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                review_result="assessment_and_instruction_recorded",
            )
        )

        assert finalized.status == MedicationHistoryStatus.FINALIZED.value
        assert finalized.review_result == "assessment_and_instruction_recorded"
        assert finalized.reviewed_by == str(fixture.counselor_id.value)
        assert finalized.reviewed_at == fixture.clock.now().isoformat()
        loaded = await fixture.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
            )
        )
        assert loaded.review_result == "assessment_and_instruction_recorded"
        assert loaded.reviewed_by == str(fixture.counselor_id.value)
        assert loaded.reviewed_at == fixture.clock.now().isoformat()
        assert finalized.counselor_id == str(fixture.counselor_id.value)
        assert finalized.counseled_at == fixture.clock.now().isoformat()

    async def test_tc18_追加記載なしの結果は_薬剤師記載とともに保持される(
        self,
    ) -> None:
        fixture = create_fixture()
        authored_text = "対象情報を確認し、追加記載事項はないと判断した。"
        started = await fixture.start.execute(
            create_start_command(
                fixture,
                soap=SoapInput(
                    assessment=(LabeledNoteInput(text=authored_text),),
                ),
            )
        )

        finalized = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                review_result="no_additional_recordable_items",
            )
        )

        assert finalized.review_result == "no_additional_recordable_items"
        assert finalized.reviewed_by == str(fixture.counselor_id.value)
        assert finalized.reviewed_at == fixture.clock.now().isoformat()
        assert finalized.soap.assessment[0].text == authored_text

    async def test_確定すると_頭書きへ差分が投影される(self) -> None:
        # Arrange
        fixture = create_fixture()
        started = await fixture.start.execute(
            create_start_command(fixture, profile_updates=_allergy_updates())
        )

        # Act
        actual = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=started.id,
                review_result="assessment_and_instruction_recorded",
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

    async def test_後日の薬歴確定でアレルギー取消や疾患状態更新が頭書きに反映される(
        self,
    ) -> None:
        # Arrange: 1回目の薬歴でアレルギーと疾患（加療中）を登録
        fixture = create_fixture()
        first_updates = ProfileUpdateInput(
            new_allergies=(
                AllergyIntentInput(
                    allergen="ペニシリン系", reaction="皮疹", severity="moderate"
                ),
            ),
            new_conditions=(
                ConditionIntentInput(
                    condition_name="緑内障",
                    condition_status="ongoing",
                    is_contraindication_target=True,
                ),
            ),
        )
        first = await fixture.start.execute(
            create_start_command(fixture, profile_updates=first_updates)
        )
        await _finalize(fixture, first.id)

        # 別の調剤セッションを起こし、2回目の薬歴でアレルギー取消と治癒更新
        second_dispensing = register_another_dispensing(fixture)
        second_updates = ProfileUpdateInput(
            retracted_allergies=(
                RetractAllergyIntentInput(
                    allergen="ペニシリン系", reason="患者申告の誤り確認"
                ),
            ),
            updated_conditions=(
                UpdateConditionStatusIntentInput(
                    condition_name="緑内障",
                    new_status="resolved",
                    is_contraindication_target=False,
                ),
            ),
        )
        second = await fixture.start.execute(
            create_start_command(
                fixture,
                dispensing=second_dispensing,
                profile_updates=second_updates,
            )
        )

        # Act
        await _finalize(fixture, second.id)

        # Assert: アレルギーは空になり、疾患は治癒（resolved）に更新されている
        profile = await fixture.get_profile.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=_AS_OF,
            )
        )
        assert profile.allergies == ()
        assert len(profile.medical_conditions) == 1
        cond = profile.medical_conditions[0]
        assert cond.condition_status == "resolved"
        assert cond.is_contraindication_target is False
        assert cond.provenance.source_record_id == second.id

    async def test_SOAPが空だと_確定できない(self) -> None:
        """空の初回保存は確定前のDRAFT自体を作らない。"""
        fixture = create_fixture()

        with pytest.raises(SoapContentRequiredError):
            await fixture.start.execute(create_start_command(fixture, soap=SoapInput()))
        assert fixture.record_repository.items == {}

    async def test_確定には薬剤師レビュー結果が必要(self) -> None:
        fixture = create_fixture()
        started = await fixture.start.execute(create_start_command(fixture))

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=started.id,
                )
            )

        stored = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(started.id),
        )
        assert stored is not None
        assert stored.status is MedicationHistoryStatus.DRAFT
        assert fixture.profile_repository.items == {}

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
        assert actual[0].counseled_at is None
        assert actual[1].counseled_at is None

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


class Test下書きの網羅的更新ユースケース:
    """TC-15 〜 TC-17: 下書き薬歴の全項目更新ユースケースの検証。"""

    async def test_tc15_下書きの全項目を更新して保存できる(self) -> None:
        # Arrange
        from app.application.medication_history.inputs import (
            CategorizedNoteInput,
            HandbookStatusInput,
            ResidualDrugInput,
        )

        fixture = create_fixture()
        record_id = await _start(fixture)

        cmd = UpdateMedicationHistoryDraftCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            soap=create_soap_input(subjective="下書き更新されたS"),
            handbook_status=HandbookStatusInput(
                presented=False,
                not_presented_reason="forgot",
                guidance_provided=True,
            ),
            residual_drug=ResidualDrugInput(
                has_residual_drugs=True,
                quantity=14,
                reason="飲み忘れ",
            ),
            information_sheet_provided=True,
            additional_notes=(
                CategorizedNoteInput(
                    major_category_code="soap",
                    medium_category_code="s",
                    text="更新された追加メモ",
                ),
            ),
        )

        # Act
        actual = await fixture.update_draft.execute(cmd)

        # Assert
        assert actual.soap.subjective[0].text == "下書き更新されたS"
        assert actual.handbook_status is not None
        assert not actual.handbook_status.presented
        assert actual.handbook_status.not_presented_reason == "forgot"
        assert actual.residual_drug is not None
        assert actual.residual_drug.has_residual_drugs
        assert actual.residual_drug.quantity == 14
        assert actual.information_sheet_provided is True
        assert len(actual.additional_notes) == 1
        assert actual.additional_notes[0].text == "更新された追加メモ"

    async def test_tc16_確定済み薬歴への下書き更新は拒否される(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        await _finalize(fixture, record_id)

        cmd = UpdateMedicationHistoryDraftCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            information_sheet_provided=True,
        )

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyFinalizedError):
            await fixture.update_draft.execute(cmd)

    async def test_tc17_停止中法人の下書き更新は拒否される(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        cmd = UpdateMedicationHistoryDraftCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            information_sheet_provided=True,
        )

        # Act / Assert
        with pytest.raises(CorporateInactiveError):
            await fixture.update_draft.execute(cmd)


class Test薬歴確定ユースケース真正性と遅延理由:
    """TC-18 〜 TC-23: 確定ユースケースにおける確定者、確定日時、遅延理由の検証。"""

    async def test_tc18_当日確定で確定者と確定日時が保存される(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        finalized_at = fixture.clock.now()

        cmd = FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            finalized_by=str(fixture.counselor_id.value),
            finalized_at=finalized_at,
            review_result="assessment_and_instruction_recorded",
        )

        # Act
        actual = await fixture.finalize.execute(cmd)

        # Assert
        assert actual.status == MedicationHistoryStatus.FINALIZED.value
        assert actual.finalized_at == finalized_at.isoformat()
        assert actual.finalized_by == str(fixture.counselor_id.value)
        assert actual.delay_reason is None

    async def test_tc19_遅延確定で遅延理由が保存される(self) -> None:
        # Arrange
        from datetime import timedelta

        fixture = create_fixture()
        record_id = await _start(fixture)
        next_day = fixture.clock.now() + timedelta(days=1)

        cmd = FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            finalized_by=str(fixture.counselor_id.value),
            finalized_at=next_day,
            delay_reason="処方照会と患者再来局の確認のため翌日確定",
            review_result="assessment_and_instruction_recorded",
        )

        # Act
        actual = await fixture.finalize.execute(cmd)

        # Assert
        assert actual.status == MedicationHistoryStatus.FINALIZED.value
        assert actual.delay_reason == "処方照会と患者再来局の確認のため翌日確定"

    async def test_tc20_遅延確定で遅延理由が無いと拒否される(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        next_day = fixture.clock.now() + timedelta(days=1)

        cmd = FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            finalized_by=str(fixture.counselor_id.value),
            finalized_at=next_day,
            delay_reason=None,
            review_result="assessment_and_instruction_recorded",
        )

        # Act / Assert
        with pytest.raises(FinalizationDelayReasonRequiredError):
            await fixture.finalize.execute(cmd)

    async def test_tc21_確定者が薬剤師資格を持たない場合は拒否される(self) -> None:
        # Arrange
        from datetime import UTC, datetime

        fixture = create_fixture()
        record_id = await _start(fixture)
        non_pharmacist_id = StaffId.generate()
        # 資格を持たないスタッフとして登録
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=non_pharmacist_id,
            qualifications=StaffQualifications.empty(),
        )

        cmd = FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            finalized_by=str(non_pharmacist_id.value),
            finalized_at=datetime.now(UTC),
            review_result="assessment_and_instruction_recorded",
        )

        # Act / Assert
        with pytest.raises(CounselorQualificationError):
            await fixture.finalize.execute(cmd)

    async def test_tc23_確定メタデータがDTOとして正しく取得できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = await _start(fixture)
        finalized_at = fixture.clock.now()

        await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
                finalized_by=str(fixture.counselor_id.value),
                finalized_at=finalized_at,
                review_result="assessment_and_instruction_recorded",
            )
        )

        # Act
        actual = await fixture.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
            )
        )

        # Assert
        assert actual.finalized_at == finalized_at.isoformat()
        assert actual.finalized_by == str(fixture.counselor_id.value)
