"""服薬期間中のフォローアップ追加ユースケーステスト。"""

from datetime import timedelta

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorRole
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.exceptions import MedicationHistoryNotFoundError
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.inputs import (
    AddFollowUpCommand,
    AllergyIntentInput,
    ProfileUpdateInput,
    SoapInput,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    MedicationHistoryDomainError,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryRecordKind,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.lifecycle import StoreStateConflictError
from app.domain.store.manager_assignment import ManagerAbsenceConflictError
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_soap_input,
    create_start_command,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_allergy_intent,
    create_independent_follow_up_record,
    create_record,
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


class TestAddFollowUpUseCase:
    """AddFollowUpUseCase の単体・結合テスト。"""

    async def test_add_follow_up_success(self) -> None:
        """TC-09: 別店舗のフォローアップを新しい下書き薬歴として保存する。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)
        source_id = MedicationHistoryRecordId.parse(record_id)
        target_store_id = StoreId.generate()
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id,
            store_id=target_store_id,
        )

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            store_id=str(target_store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(
                subjective=(create_soap_input().subjective[0],),
            ),
        )

        dto = await fixture.add_follow_up.execute(command)

        assert dto.id != record_id
        assert dto.record_kind == MedicationHistoryRecordKind.FOLLOW_UP.value
        assert dto.source_record_id == record_id
        assert dto.store_id == str(target_store_id.value)
        assert dto.patient_id == str(fixture.patient_id.value)
        assert dto.dispensing_id == str(fixture.dispensing.id.value)
        assert dto.prescription_id == str(fixture.dispensing.prescription_id.value)
        assert dto.status == "draft"

        parent = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=source_id,
        )
        child = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(dto.id),
        )
        assert parent is not None
        assert parent.follow_ups == ()
        assert child is not None
        assert child.source_record_id == source_id
        assert child.recorded_by == fixture.counselor_id
        assert len(fixture.record_repository.items) == 2

    async def test_tc10_確定済み店舗横断フォローアップから次の店舗へ連鎖できる(
        self,
    ) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        store_b = StoreId.generate()
        store_c = StoreId.generate()
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id, store_id=store_b
        )
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id, store_id=store_c
        )
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert source is not None
        assert source.counseled_at is not None
        first_followed_up_at = source.counseled_at.value + timedelta(days=3)

        first = await fixture.add_follow_up.execute(
            AddFollowUpCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=source_id,
                store_id=str(store_b.value),
                patient_id=str(fixture.patient_id.value),
                counselor_id=str(fixture.counselor_id.value),
                followed_up_at=first_followed_up_at,
                method="telephone",
                soap=create_soap_input(),
            )
        )
        assert first.id != source_id
        assert first.record_kind == MedicationHistoryRecordKind.FOLLOW_UP.value
        assert first.source_record_id == source_id
        fixture.clock.advance(
            first_followed_up_at - fixture.clock.now() + timedelta(hours=1)
        )
        first_final = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=first.id,
                review_result="assessment_and_instruction_recorded",
            )
        )
        second = await fixture.add_follow_up.execute(
            AddFollowUpCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=first_final.id,
                store_id=str(store_c.value),
                patient_id=str(fixture.patient_id.value),
                counselor_id=str(fixture.counselor_id.value),
                followed_up_at=first_followed_up_at + timedelta(days=3),
                method="telephone",
                soap=create_soap_input(),
            )
        )

        assert first_final.source_record_id == source_id
        assert second.record_kind == MedicationHistoryRecordKind.FOLLOW_UP.value
        assert second.source_record_id == first_final.id
        assert second.store_id == str(store_c.value)
        assert second.patient_id == str(fixture.patient_id.value)
        assert second.dispensing_id == str(fixture.dispensing.id.value)

    @pytest.mark.parametrize(
        "time_delta",
        (timedelta(0), timedelta(seconds=-1)),
        ids=("同時刻", "参照元より前"),
    )
    async def test_tc12_参照元と同時刻またはそれ以前のフォローアップを拒否する(
        self, time_delta: timedelta
    ) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert source is not None
        assert source.counseled_at is not None
        followed_up_at = source.counseled_at.value + time_delta
        before_count = len(fixture.record_repository.items)

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=followed_up_at,
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert len(fixture.record_repository.items) == before_count

    async def test_tc13_同一法人でも別患者の参照元は404として拒否する(self) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)

        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(PatientId.generate().value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert len(fixture.record_repository.items) == 1

    async def test_tc14_操作範囲外の対象店舗は参照元を読む前に404になる(self) -> None:
        fixture = create_fixture(store_role=ActorRole.STORE_OPERATOR)
        source_id = await _create_and_finalize_record(fixture)
        target_store = StoreId.generate()
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id, store_id=target_store
        )
        before_reads = fixture.record_repository.get_calls

        with pytest.raises(TenantBoundaryNotFoundError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(target_store.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert fixture.record_repository.get_calls == before_reads
        assert len(fixture.record_repository.items) == 1

    async def test_tc15_店舗閲覧者は参照元を読む前に起票を拒否する(self) -> None:
        fixture = create_fixture(store_role=ActorRole.STORE_VIEWER)

        source = finalize_record_with_review(
            create_record(
                corporate_id=fixture.corporate_id,
                store_id=fixture.store_id,
                patient_id=fixture.patient_id,
                dispensing_id=fixture.dispensing.id,
                prescription_id=fixture.dispensing.prescription_id,
            )
        )
        await fixture.record_repository.save(source)
        source_id = str(source.id.value)
        before_reads = fixture.record_repository.get_calls

        with pytest.raises(AuthorizationError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert fixture.record_repository.get_calls == before_reads

    async def test_tc17_休止店舗では参照元取得前に新規業務を拒否する(self) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        fixture.store_operations.failures[(fixture.corporate_id, fixture.store_id)] = (
            StoreStateConflictError()
        )
        before_reads = fixture.record_repository.get_calls

        with pytest.raises(StoreStateConflictError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert fixture.record_repository.get_calls == before_reads

    async def test_tc18_管理薬剤師が不在なら参照元取得前に拒否する(self) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        fixture.store_operations.failures[(fixture.corporate_id, fixture.store_id)] = (
            ManagerAbsenceConflictError()
        )
        before_reads = fixture.record_repository.get_calls

        with pytest.raises(ManagerAbsenceConflictError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert fixture.record_repository.get_calls == before_reads

    async def test_tc20_未解決Actorからのフォローアップ記載を拒否する(self) -> None:
        from app.application.access_control.models import ResolvedActorContext
        from app.domain.identity.primitives import AccountPersonId, UserAccountId

        actor = ResolvedActorContext(
            principal_id="unresolved-staff",
            roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            staff_id=None,
        )
        fixture = create_fixture(actor=actor)
        source = finalize_record_with_review(
            create_record(
                corporate_id=fixture.corporate_id,
                store_id=fixture.store_id,
                patient_id=fixture.patient_id,
                dispensing_id=fixture.dispensing.id,
                prescription_id=fixture.dispensing.prescription_id,
            )
        )
        await fixture.record_repository.save(source)

        with pytest.raises(AuthorizationError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(source.id.value),
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=create_soap_input(),
                )
            )

        assert len(fixture.record_repository.items) == 1

    async def test_tc21_SOAPも追加メモも空のフォローアップを拒否する(self) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.add_follow_up.execute(
                AddFollowUpCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=source_id,
                    store_id=str(fixture.store_id.value),
                    patient_id=str(fixture.patient_id.value),
                    counselor_id=str(fixture.counselor_id.value),
                    followed_up_at=COUNSELED_AT + timedelta(days=3),
                    method="telephone",
                    soap=SoapInput(),
                )
            )

        assert len(fixture.record_repository.items) == 1

    async def test_add_follow_up_saves_profile_updates(self) -> None:
        """TC-26: 下書きの頭書き差分は確定まで投影されない。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(
                subjective=(create_soap_input().subjective[0],),
            ),
            profile_updates=ProfileUpdateInput(
                new_allergies=(
                    AllergyIntentInput(
                        allergen="ペニシリン系", reaction="皮疹", severity="severe"
                    ),
                )
            ),
        )

        dto = await fixture.add_follow_up.execute(command)
        assert dto.updates_profile is True
        assert dto.record_kind == MedicationHistoryRecordKind.FOLLOW_UP.value

        # 頭書きリポジトリに反映されていることを確認
        profile = await fixture.profile_repository.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
        assert profile is not None
        assert profile.allergies == ()

    async def test_tc27_独立フォローアップ確定時の差分は自身を由来として投影する(
        self,
    ) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert source is not None
        assert source.counseled_at is not None
        target_store_id = StoreId.generate()
        fixture.store_reference.register(
            corporate_id=fixture.corporate_id,
            store_id=target_store_id,
        )
        occurred_at = source.counseled_at.value + timedelta(days=3)

        draft = await fixture.add_follow_up.execute(
            AddFollowUpCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=source_id,
                store_id=str(target_store_id.value),
                patient_id=str(fixture.patient_id.value),
                counselor_id=str(fixture.counselor_id.value),
                followed_up_at=occurred_at,
                method="telephone",
                soap=create_soap_input(),
                profile_updates=ProfileUpdateInput(
                    new_allergies=(
                        AllergyIntentInput(
                            allergen="ペニシリン系",
                            reaction="皮疹",
                            severity="severe",
                        ),
                    )
                ),
            )
        )
        fixture.clock.advance(occurred_at - fixture.clock.now() + timedelta(hours=1))
        finalized = await fixture.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=draft.id,
                review_result="assessment_and_instruction_recorded",
            )
        )

        profile = await fixture.profile_repository.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )

        assert finalized.id == draft.id
        assert finalized.record_kind == MedicationHistoryRecordKind.FOLLOW_UP.value
        assert finalized.source_record_id == source_id
        assert finalized.store_id == str(target_store_id.value)
        assert profile is not None
        assert len(profile.allergies) == 1
        provenance = profile.allergies[0].provenance
        assert provenance.source_record_id == MedicationHistoryRecordId.parse(draft.id)
        assert provenance.recorded_by == fixture.counselor_id
        assert provenance.recorded_on == occurred_at.date()
        assert source is not None
        assert source.follow_ups == ()

    async def test_tc28_レビュー結果のない独立フォローアップは確定も投影もしない(
        self,
    ) -> None:
        fixture = create_fixture()
        source_id = await _create_and_finalize_record(fixture)
        source = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(source_id),
        )
        assert source is not None
        draft = create_independent_follow_up_record(
            source,
            store_id=StoreId.generate(),
            counseled_at=COUNSELED_AT + timedelta(days=3),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン系"),)
            ),
        )
        await fixture.record_repository.save(draft)
        profile_before = await fixture.profile_repository.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )

        with pytest.raises(MedicationHistoryDomainError):
            await fixture.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(draft.id.value),
                )
            )

        stored = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=draft.id,
        )
        profile_after = await fixture.profile_repository.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
        assert stored is not None
        assert stored.status.value == "draft"
        assert profile_after == profile_before

    async def test_add_follow_up_without_profile_updates_skips_profile_save(
        self,
    ) -> None:
        """TC-APP-03: 頭書き差分が無い場合、頭書きの保存処理はスキップされる。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(
                subjective=(create_soap_input().subjective[0],),
            ),
            profile_updates=ProfileUpdateInput(),
        )

        dto = await fixture.add_follow_up.execute(command)
        assert dto.updates_profile is False

    async def test_add_follow_up_record_not_found(self) -> None:
        """TC-APP-04: 存在しない薬歴IDへのフォローアップ追加はNotFoundErrorになる。"""
        fixture = create_fixture()
        dummy_id = str(MedicationHistoryRecordId.generate().value)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=dummy_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(subjective=(create_soap_input().subjective[0],)),
        )

        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.add_follow_up.execute(command)

    async def test_add_follow_up_non_pharmacist_rejected(self) -> None:
        """TC-APP-05: 薬剤師資格を持たないスタッフによるフォローアップ記録は拒否される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # 資格を持たないスタッフを登録
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(clerk_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(subjective=(create_soap_input().subjective[0],)),
        )

        with pytest.raises(CounselorQualificationError):
            await fixture.add_follow_up.execute(command)

    async def test_add_follow_up_inactive_corporate_rejected(self) -> None:
        """TC-APP-06: 停止中法人によるフォローアップ追加は認可拒否される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        # 法人を停止状態にする
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(subjective=(create_soap_input().subjective[0],)),
        )

        with pytest.raises(CorporateInactiveError):
            await fixture.add_follow_up.execute(command)

    async def test_add_follow_up_tenant_isolation(self) -> None:
        """TC-APP-07: 別法人の薬歴IDを指定した場合は404として隠蔽される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        other_corporate_id = str(CorporateId.generate().value)

        command = AddFollowUpCommand(
            corporate_id=other_corporate_id,
            record_id=record_id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(subjective=(create_soap_input().subjective[0],)),
        )

        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.add_follow_up.execute(command)
