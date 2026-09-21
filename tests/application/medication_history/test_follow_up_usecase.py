"""服薬期間中のフォローアップ追加ユースケーステスト。"""

from datetime import timedelta

import pytest

from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history import (
    AddFollowUpCommand,
    AllergyIntentInput,
    FinalizeMedicationHistoryCommand,
    MedicationHistoryNotFoundError,
    ProfileUpdateInput,
    SoapInput,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    CounselorQualificationError,
    MedicationHistoryRecordId,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_soap_input,
    create_start_command,
)
from tests.factories.medication_history_factory import COUNSELED_AT


async def _create_and_finalize_record(fixture: MedicationHistoryFixture) -> str:
    """テスト用に確定済みの薬歴を作成してレコードID文字列を返す。"""
    draft = await fixture.start.execute(create_start_command(fixture))
    finalized = await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=draft.corporate_id,
            record_id=draft.id,
        )
    )
    return str(finalized.id)


class TestAddFollowUpUseCase:
    """AddFollowUpUseCase の単体・結合テスト。"""

    async def test_add_follow_up_success(self) -> None:
        """TC-APP-01: 確定済み薬歴にフォローアップを追加し、更新後DTOに反映される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(
                subjective=(create_soap_input().subjective[0],),
            ),
        )

        dto = await fixture.add_follow_up.execute(command)

        assert len(dto.follow_ups) == 1
        fu = dto.follow_ups[0]
        assert fu.counselor_id == str(fixture.counselor_id.value)
        assert fu.method == "telephone"
        assert len(fu.soap.subjective) == 1

        # 永続化された集約を直接確認
        loaded = await fixture.record_repository.get(
            corporate_id=fixture.corporate_id,
            record_id=MedicationHistoryRecordId.parse(record_id),
        )
        assert loaded is not None
        assert len(loaded.follow_ups) == 1

    async def test_add_follow_up_saves_profile_updates(self) -> None:
        """TC-APP-02: 頭書き差分がある場合、薬歴と同時に頭書きも更新保存される。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
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
        assert dto.follow_ups[0].updates_profile is True

        # 頭書きリポジトリに反映されていることを確認
        profile = await fixture.profile_repository.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
        assert profile is not None
        assert len(profile.allergies) == 1
        assert profile.allergies[0].allergen.value == "ペニシリン系"

    async def test_add_follow_up_without_profile_updates_skips_profile_save(
        self,
    ) -> None:
        """TC-APP-03: 頭書き差分が無い場合、頭書きの保存処理はスキップされる。"""
        fixture = create_fixture()
        record_id = await _create_and_finalize_record(fixture)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(
                subjective=(create_soap_input().subjective[0],),
            ),
            profile_updates=ProfileUpdateInput(),
        )

        dto = await fixture.add_follow_up.execute(command)
        assert dto.follow_ups[0].updates_profile is False

    async def test_add_follow_up_record_not_found(self) -> None:
        """TC-APP-04: 存在しない薬歴IDへのフォローアップ追加はNotFoundErrorになる。"""
        fixture = create_fixture()
        dummy_id = str(MedicationHistoryRecordId.generate().value)

        command = AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=dummy_id,
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
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method="telephone",
            soap=SoapInput(subjective=(create_soap_input().subjective[0],)),
        )

        with pytest.raises(MedicationHistoryNotFoundError):
            await fixture.add_follow_up.execute(command)
