"""患者ライフサイクル・名寄せ統合ユースケースのテスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.patient.change_patient_birth_date import (
    ChangePatientBirthDateCommand,
    ChangePatientBirthDateUseCase,
)
from app.application.patient.change_patient_names import (
    ChangePatientNamesCommand,
    ChangePatientNamesUseCase,
)
from app.application.patient.deactivate_patient import (
    DeactivatePatientCommand,
    DeactivatePatientUseCase,
)
from app.application.patient.exceptions import PatientNotFoundError
from app.application.patient.get_patient import GetPatientQuery, GetPatientUseCase
from app.application.patient.merge_patients import (
    MergePatientsCommand,
    MergePatientsUseCase,
)
from app.application.patient.reactivate_patient import (
    ReactivatePatientCommand,
    ReactivatePatientUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientStateConflictError
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientBirthDate, PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository


def _resolved_vendor_actor() -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="test-vendor-admin",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )


def _unresolved_vendor_actor() -> ActorContext:
    return ActorContext.vendor_system_admin(principal_id="unresolved-admin")


def _corporate_access(actor: ActorContext) -> CorporateAccessService:
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(),
        AuthorizationService(actor),
    )


async def _setup_patient(
    repository: InMemoryPatientRepository,
    corporate_id: CorporateId,
    *,
    last_name: str = "山田",
    first_name: str = "太郎",
) -> Patient:
    patient = Patient.create(
        corporate_id=corporate_id,
        names=PersonNames.create(
            last_name=last_name,
            first_name=first_name,
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
        patient_number=await repository.allocate_patient_number(corporate_id),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
    )

    await repository.save(patient)
    return patient


# ==============================================================================
# TC-23, TC-24: DeactivatePatientUseCase
# ==============================================================================


async def test_TC23_患者無効化ユースケース_正常系() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    use_case = DeactivatePatientUseCase(repository, access, clock)
    await use_case.execute(
        DeactivatePatientCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            reason="患者死亡による利用停止",
        )
    )

    saved = await repository.get(corporate_id=corporate_id, patient_id=patient.id)
    assert saved is not None
    assert saved.status.value == "inactive"
    assert saved.is_active is False
    assert len(saved.status_history) == 1
    assert saved.status_history[0].reason.value == "患者死亡による利用停止"
    assert saved.status_history[0].person_id == actor.person_id


async def test_TC24_患者無効化ユースケース_認可および不在検証() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))

    # 未特定Actorの場合
    unresolved_access = _corporate_access(_unresolved_vendor_actor())
    unresolved_use_case = DeactivatePatientUseCase(repository, unresolved_access, clock)
    with pytest.raises(AuthorizationError, match="本人とアカウントの特定が必要"):
        await unresolved_use_case.execute(
            DeactivatePatientCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                reason="利用停止",
            )
        )

    # 存在しない患者の場合
    resolved_access = _corporate_access(_resolved_vendor_actor())
    resolved_use_case = DeactivatePatientUseCase(repository, resolved_access, clock)
    with pytest.raises(PatientNotFoundError):
        await resolved_use_case.execute(
            DeactivatePatientCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(PatientId.generate().value),
                reason="利用停止",
            )
        )


# ==============================================================================
# TC-25: ReactivatePatientUseCase
# ==============================================================================


async def test_TC25_患者再有効化ユースケース_正常系() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    # まず無効化
    deactivate_uc = DeactivatePatientUseCase(repository, access, clock)
    await deactivate_uc.execute(
        DeactivatePatientCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            reason="誤無効化",
        )
    )

    # 再有効化
    reactivate_uc = ReactivatePatientUseCase(repository, access, clock)
    await reactivate_uc.execute(
        ReactivatePatientCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            reason="再来局に伴い再有効化",
        )
    )

    saved = await repository.get(corporate_id=corporate_id, patient_id=patient.id)
    assert saved is not None
    assert saved.status.value == "active"
    assert saved.is_active is True
    assert len(saved.status_history) == 2


# ==============================================================================
# TC-26, TC-27: MergePatientsUseCase
# ==============================================================================


async def test_TC26_患者マージユースケース_正常系() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    source = await _setup_patient(repository, corporate_id, last_name="山田旧姓")
    target = await _setup_patient(repository, corporate_id, last_name="田中新姓")
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    merge_uc = MergePatientsUseCase(repository, access, clock)
    result = await merge_uc.execute(
        MergePatientsCommand(
            corporate_id=str(corporate_id.value),
            source_patient_id=str(source.id.value),
            target_patient_id=str(target.id.value),
            reason="改姓による重複登録解消",
        )
    )

    assert result.source_patient_id == str(source.id.value)
    assert result.target_patient_id == str(target.id.value)

    saved_source = await repository.get(corporate_id=corporate_id, patient_id=source.id)
    assert saved_source is not None
    assert saved_source.status.value == "merged"
    assert saved_source.is_merged is True
    assert saved_source.merged_into_id == target.id

    saved_target = await repository.get(corporate_id=corporate_id, patient_id=target.id)
    assert saved_target is not None
    assert saved_target.status.value == "active"


async def test_TC27_患者マージユースケース_異常系() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    source = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    merge_uc = MergePatientsUseCase(repository, access, clock)

    # ターゲットが存在しない場合
    with pytest.raises(PatientNotFoundError):
        await merge_uc.execute(
            MergePatientsCommand(
                corporate_id=str(corporate_id.value),
                source_patient_id=str(source.id.value),
                target_patient_id=str(PatientId.generate().value),
                reason="名寄せ",
            )
        )

    # ソースが存在しない場合
    with pytest.raises(PatientNotFoundError):
        await merge_uc.execute(
            MergePatientsCommand(
                corporate_id=str(corporate_id.value),
                source_patient_id=str(PatientId.generate().value),
                target_patient_id=str(source.id.value),
                reason="名寄せ",
            )
        )

    # 自身へマージしようとした場合
    with pytest.raises(PatientStateConflictError, match="同一の患者"):
        await merge_uc.execute(
            MergePatientsCommand(
                corporate_id=str(corporate_id.value),
                source_patient_id=str(source.id.value),
                target_patient_id=str(source.id.value),
                reason="名寄せ",
            )
        )


# ==============================================================================
# TC-28: GetPatientUseCase (状態情報取得)
# ==============================================================================


async def test_TC28_患者取得ユースケース_状態情報取得() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    source = await _setup_patient(repository, corporate_id)
    target = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    merge_uc = MergePatientsUseCase(repository, access, clock)
    await merge_uc.execute(
        MergePatientsCommand(
            corporate_id=str(corporate_id.value),
            source_patient_id=str(source.id.value),
            target_patient_id=str(target.id.value),
            reason="名寄せ",
        )
    )

    get_uc = GetPatientUseCase(repository, access)
    dto = await get_uc.execute(
        GetPatientQuery(
            corporate_id=str(corporate_id.value),
            patient_id=str(source.id.value),
        )
    )

    assert dto.status == "merged"
    assert dto.merged_into_id == str(target.id.value)
    assert len(dto.status_history) == 1
    assert dto.status_history[0].after == "merged"
    assert dto.status_history[0].merged_into_id == str(target.id.value)


# ==============================================================================
# TC-29: 統合済み患者の属性変更ユースケース拒否
# ==============================================================================


async def test_TC29_統合済み患者の属性変更ユースケース_拒否() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    source = await _setup_patient(repository, corporate_id)
    target = await _setup_patient(repository, corporate_id)
    clock = FakeClock(datetime(2026, 9, 21, 10, 0, tzinfo=UTC))
    actor = _resolved_vendor_actor()
    access = _corporate_access(actor)

    merge_uc = MergePatientsUseCase(repository, access, clock)
    await merge_uc.execute(
        MergePatientsCommand(
            corporate_id=str(corporate_id.value),
            source_patient_id=str(source.id.value),
            target_patient_id=str(target.id.value),
            reason="名寄せ",
        )
    )

    change_names_uc = ChangePatientNamesUseCase(repository, access, clock)
    with pytest.raises(
        PatientStateConflictError, match="統合済みの患者の情報は変更できません"
    ):
        await change_names_uc.execute(
            ChangePatientNamesCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(source.id.value),
                last_name="新姓",
                first_name="太郎",
                last_name_kana="シンセイ",
                first_name_kana="タロウ",
            )
        )

    change_birth_uc = ChangePatientBirthDateUseCase(repository, access, clock)
    with pytest.raises(
        PatientStateConflictError, match="統合済みの患者の情報は変更できません"
    ):
        await change_birth_uc.execute(
            ChangePatientBirthDateCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(source.id.value),
                birth_date=date(1991, 1, 1),
            )
        )
