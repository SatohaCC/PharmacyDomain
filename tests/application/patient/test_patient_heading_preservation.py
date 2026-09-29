"""患者頭書きが基本情報・薬歴の既存処理から独立して保たれることを確認する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileQuery,
    RebuildPatientMedicalProfileCommand,
)
from app.application.medication_history.inputs import (
    AllergyIntentInput,
    ProfileUpdateInput,
)
from app.application.patient.change_patient_birth_date import (
    ChangePatientBirthDateCommand,
    ChangePatientBirthDateUseCase,
)
from app.application.patient.change_patient_heading import (
    ChangePatientHeadingCommand,
    ChangePatientHeadingUseCase,
)
from app.application.patient.change_patient_names import (
    ChangePatientNamesCommand,
    ChangePatientNamesUseCase,
)
from app.application.patient.change_patient_profile import (
    ChangePatientProfileCommand,
    ChangePatientProfileUseCase,
)
from app.application.patient.deactivate_patient import (
    DeactivatePatientCommand,
    DeactivatePatientUseCase,
)
from app.application.patient.merge_patients import (
    MergePatientsCommand,
    MergePatientsUseCase,
)
from app.application.patient.reactivate_patient import (
    ReactivatePatientCommand,
    ReactivatePatientUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.patient.heading import (
    PatientHeadingContent,
    PatientHeadingRevision,
    PatientHeadingText,
)
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.application.medication_history.helpers import (
    create_fixture as create_medication_history_fixture,
)
from tests.application.medication_history.helpers import (
    create_start_command,
)
from tests.application.medication_history.test_fact_correction_usecase import (
    _execute as execute_fact_correction,
)
from tests.application.medication_history.test_fact_correction_usecase import (
    _stored_record,
)
from tests.domain.medication_history.test_fact_correction import _element_id
from tests.factories.medication_history_factory import create_allergy_intent
from tests.factories.persistence_factory import create_patient
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository

_NOW = datetime(2026, 9, 10, 3, tzinfo=UTC)


def _revision(summary: str, notes: str | None = None) -> PatientHeadingRevision:
    """固定した改訂内容を持つ患者頭書きを作る。"""
    return PatientHeadingRevision(
        content=PatientHeadingContent(
            summary=PatientHeadingText(summary),
            notes=PatientHeadingText(notes) if notes is not None else None,
        ),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=_NOW,
    )


def _headed_patient(
    corporate_id: CorporateId, *, patient_id: PatientId | None = None, summary: str
) -> Patient:
    """指定した患者IDへ既存の頭書きを設定する。"""
    patient = create_patient(corporate_id=corporate_id)
    if patient_id is not None:
        patient = replace(patient, id=patient_id)
    return replace(patient, heading_history=(_revision(summary, "変更前の申し送り"),))


def _vendor_access() -> CorporateAccessService:
    actor = ResolvedActorContext(
        principal_id="頭書き保持テスト",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )


def _allergy_input() -> ProfileUpdateInput:
    """臨床プロファイルへ反映するアレルギー差分を作る。"""
    return ProfileUpdateInput(
        new_allergies=(
            AllergyIntentInput(
                allergen="ペニシリン系", reaction="皮疹", severity="moderate"
            ),
        )
    )


@pytest.mark.asyncio
async def test_tc43_28_頭書き更新は薬歴と臨床投影を変更しない() -> None:
    fixture = create_medication_history_fixture()
    patient_repository = InMemoryPatientRepository()
    patient = _headed_patient(
        fixture.corporate_id, patient_id=fixture.patient_id, summary="既存の概要"
    )
    await patient_repository.save(patient)
    started = await fixture.start.execute(
        create_start_command(fixture, profile_updates=_allergy_input())
    )
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    records_before = dict(fixture.record_repository.items)
    profiles_before = dict(fixture.profile_repository.items)
    assert len(profiles_before) == 1

    await ChangePatientHeadingUseCase(
        patient_repository, _vendor_access(), fixture.clock
    ).execute(
        ChangePatientHeadingCommand(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            expected_revision=1,
            provided_fields=frozenset({"notes"}),
            notes="臨床投影と独立した申し送り",
        )
    )

    saved = await patient_repository.get(
        corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
    )
    assert saved is not None
    assert saved.heading_history[-1].content.notes == PatientHeadingText(
        "臨床投影と独立した申し送り"
    )
    assert fixture.record_repository.items == records_before
    assert fixture.profile_repository.items == profiles_before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["氏名", "生年月日", "プロフィール"])
async def test_tc43_46_基本情報変更は頭書き全改訂を保持する(
    operation: str,
) -> None:
    corporate_id = CorporateId.generate()
    patient = _headed_patient(corporate_id, summary="基本情報変更前")
    repository = InMemoryPatientRepository()
    await repository.save(patient)
    access = _vendor_access()
    clock = FakeClock(_NOW)
    identity = {
        "corporate_id": str(corporate_id.value),
        "patient_id": str(patient.id.value),
    }

    if operation == "氏名":
        await ChangePatientNamesUseCase(repository, access, clock).execute(
            ChangePatientNamesCommand(
                **identity,
                last_name="別姓",
                first_name="別名",
                last_name_kana="ベツセイ",
                first_name_kana="ベツメイ",
            )
        )
    elif operation == "生年月日":
        await ChangePatientBirthDateUseCase(repository, access, clock).execute(
            ChangePatientBirthDateCommand(**identity, birth_date=date(1988, 2, 3))
        )
    else:
        await ChangePatientProfileUseCase(repository, access, clock).execute(
            ChangePatientProfileCommand(
                **identity,
                provided_fields=frozenset({"address"}),
                address="東京都千代田区",
            )
        )

    saved = await repository.get(corporate_id=corporate_id, patient_id=patient.id)
    assert saved is not None
    assert saved.heading_history == patient.heading_history
    assert saved.profile_history


@pytest.mark.asyncio
async def test_tc43_47_無効化再有効化と名寄せは頭書きを移動しない() -> None:
    corporate_id = CorporateId.generate()
    source = _headed_patient(corporate_id, summary="統合元の申し送り")
    target = _headed_patient(corporate_id, summary="統合先の申し送り")
    repository = InMemoryPatientRepository()
    await repository.save(source)
    await repository.save(target)
    access = _vendor_access()
    clock = FakeClock(_NOW)
    identity = {
        "corporate_id": str(corporate_id.value),
        "patient_id": str(source.id.value),
    }

    await DeactivatePatientUseCase(repository, access, clock).execute(
        DeactivatePatientCommand(**identity, reason="利用停止")
    )
    await ReactivatePatientUseCase(repository, access, clock).execute(
        ReactivatePatientCommand(**identity, reason="利用再開")
    )
    await MergePatientsUseCase(repository, access, clock).execute(
        MergePatientsCommand(
            corporate_id=str(corporate_id.value),
            source_patient_id=str(source.id.value),
            target_patient_id=str(target.id.value),
            reason="重複患者の統合",
        )
    )

    saved_source = await repository.get(corporate_id=corporate_id, patient_id=source.id)
    saved_target = await repository.get(corporate_id=corporate_id, patient_id=target.id)
    assert saved_source is not None
    assert saved_target is not None
    assert saved_source.heading_history == source.heading_history
    assert len(saved_source.status_history) == 3
    assert saved_target.heading_history == target.heading_history


@pytest.mark.asyncio
async def test_tc43_49_薬歴の下書き作成は患者頭書きを変更しない() -> None:
    fixture = create_medication_history_fixture()
    repository = InMemoryPatientRepository()
    patient = _headed_patient(
        fixture.corporate_id, patient_id=fixture.patient_id, summary="薬歴作成前"
    )
    await repository.save(patient)

    started = await fixture.start.execute(
        create_start_command(fixture, profile_updates=_allergy_input())
    )

    saved = await repository.get(
        corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
    )
    assert started.status == "draft"
    assert fixture.profile_repository.items == {}
    assert saved is not None
    assert saved.heading_history == patient.heading_history


@pytest.mark.asyncio
async def test_tc43_50_薬歴確定の臨床投影は患者頭書きから独立する() -> None:
    fixture = create_medication_history_fixture()
    repository = InMemoryPatientRepository()
    patient = _headed_patient(
        fixture.corporate_id, patient_id=fixture.patient_id, summary="確定前"
    )
    await repository.save(patient)
    started = await fixture.start.execute(
        create_start_command(fixture, profile_updates=_allergy_input())
    )

    finalized = await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    profile = await fixture.get_profile.execute(
        GetPatientMedicalProfileQuery(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            as_of=date(2026, 8, 24),
        )
    )
    saved = await repository.get(
        corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
    )

    assert finalized.status == "finalized"
    assert len(profile.allergies) == 1
    assert saved is not None
    assert saved.heading_history == patient.heading_history


@pytest.mark.asyncio
async def test_tc43_51_確定薬歴の事実訂正は患者頭書きを変更しない() -> None:
    fixture = create_medication_history_fixture()
    repository = InMemoryPatientRepository()
    patient = _headed_patient(
        fixture.corporate_id, patient_id=fixture.patient_id, summary="訂正前"
    )
    await repository.save(patient)
    record = await _stored_record(
        fixture,
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),)),
    )
    target = _element_id(record, "profile_updates.new_allergies", 0)
    await execute_fact_correction(fixture, record, target=target, operation="retract")
    profile = await fixture.get_profile.execute(
        GetPatientMedicalProfileQuery(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            as_of=date(2026, 8, 24),
        )
    )

    saved = await repository.get(
        corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
    )
    assert fixture.record_repository.items[record.id].fact_corrections
    assert profile.allergies == ()
    assert saved is not None
    assert saved.heading_history == patient.heading_history


@pytest.mark.asyncio
async def test_tc43_52_臨床プロファイル再構築は患者頭書きを保持する() -> None:
    fixture = create_medication_history_fixture()
    repository = InMemoryPatientRepository()
    patient = _headed_patient(
        fixture.corporate_id, patient_id=fixture.patient_id, summary="再構築前"
    )
    await repository.save(patient)
    started = await fixture.start.execute(
        create_start_command(fixture, profile_updates=_allergy_input())
    )
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )

    rebuilt = await fixture.rebuild_profile.execute(
        RebuildPatientMedicalProfileCommand(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            as_of=date(2026, 8, 24),
        )
    )
    saved = await repository.get(
        corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
    )

    assert len(rebuilt.allergies) == 1
    assert saved is not None
    assert saved.heading_history == patient.heading_history
