"""患者頭書きUseCaseの認可・変更・履歴。"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.exceptions import CorporateInactiveError
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
from app.application.patient.exceptions import PatientNotFoundError
from app.application.patient.get_patient_heading import (
    GetPatientHeadingQuery,
    GetPatientHeadingUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.exceptions import (
    PatientHeadingConflictError,
    PatientStateConflictError,
)
from app.domain.patient.heading import (
    PatientHeadingContent,
    PatientHeadingRevision,
    PatientHeadingText,
)
from app.domain.patient.lifecycle import PatientStatus
from app.domain.patient.primitives import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.persistence_factory import create_patient
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository

_NOW = datetime(2026, 9, 10, 3, tzinfo=UTC)


def _actor(
    corporate_id: CorporateId,
    role: ActorRole = ActorRole.STORE_OPERATOR,
) -> ResolvedActorContext:
    """指定した権限を持つ本人特定済みActorを組み立てる。"""
    return ResolvedActorContext(
        principal_id="test-principal",
        roles=frozenset({role}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )


def _access(actor: ActorContext) -> CorporateAccessService:
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )


def _content(summary: str | None, notes: str | None = None) -> PatientHeadingContent:
    return PatientHeadingContent(
        summary=PatientHeadingText(summary) if summary is not None else None,
        notes=PatientHeadingText(notes) if notes is not None else None,
    )


def _revision(summary: str, at: datetime = _NOW) -> PatientHeadingRevision:
    return PatientHeadingRevision(
        content=_content(summary),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=at,
    )


@pytest.mark.asyncio
async def test_tc43_13_未登録患者頭書きは空の参照DTOを返す() -> None:
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    save_calls = repository.save_calls
    use_case = GetPatientHeadingUseCase(repository, _access(_actor(corporate_id)))

    dto = await use_case.execute(
        GetPatientHeadingQuery(
            corporate_id=str(corporate_id.value), patient_id=str(patient.id.value)
        )
    )

    assert dto.patient_id == str(patient.id.value)
    assert dto.revision == 0
    assert (dto.summary, dto.notes) == (None, None)
    assert (dto.updated_by_person_id, dto.updated_by_account_id, dto.updated_at) == (
        None,
        None,
        None,
    )
    assert dto.history == ()
    assert repository.save_calls == save_calls


@pytest.mark.asyncio
async def test_tc43_14_参照DTOは履歴末尾と改訂者を返す() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    first = _revision("前の概要")
    second = _revision("現在の概要", datetime(2026, 9, 11, 4, tzinfo=UTC))
    patient = replace(
        create_patient(corporate_id=corporate_id), heading_history=(first, second)
    )
    await repository.save(patient)

    dto = await GetPatientHeadingUseCase(
        repository, _access(_actor(corporate_id))
    ).execute(
        GetPatientHeadingQuery(
            corporate_id=str(corporate_id.value), patient_id=str(patient.id.value)
        )
    )

    assert dto.revision == 2
    assert dto.summary == "現在の概要"
    assert dto.updated_by_person_id == str(second.person_id.value)
    assert dto.updated_by_account_id == str(second.account_id.value)
    assert dto.updated_at == second.recorded_at.isoformat()
    assert [revision.revision for revision in dto.history] == [1, 2]
    assert [revision.summary for revision in dto.history] == ["前の概要", "現在の概要"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fields", "summary", "notes"),
    [
        (frozenset({"summary"}), "新しい概要", None),
        (frozenset({"notes"}), None, "新しい申し送り"),
        (frozenset({"summary", "notes"}), "新しい概要", "新しい申し送り"),
    ],
    ids=["概要だけ", "申し送りだけ", "両方"],
)
async def test_tc43_15_指定した頭書き項目だけを更新する(
    fields: frozenset[str], summary: str | None, notes: str | None
) -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    first = PatientHeadingRevision(
        content=_content("元の概要", "元の申し送り"),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=_NOW,
    )
    patient = replace(
        create_patient(corporate_id=corporate_id), heading_history=(first,)
    )
    await repository.save(patient)
    actor = _actor(corporate_id)
    use_case = ChangePatientHeadingUseCase(repository, _access(actor), FakeClock(_NOW))

    dto = await use_case.execute(
        ChangePatientHeadingCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            expected_revision=1,
            provided_fields=fields,
            summary=summary,
            notes=notes,
        )
    )

    expected_summary = summary if "summary" in fields else "元の概要"
    expected_notes = notes if "notes" in fields else "元の申し送り"
    assert (dto.summary, dto.notes) == (expected_summary, expected_notes)
    assert dto.revision == 2
    assert dto.history[0].summary == "元の概要"
    assert dto.history[0].notes == "元の申し送り"
    assert dto.history[-1].person_id == str(actor.person_id.value)


@pytest.mark.asyncio
async def test_tc43_16_空文字は解除し前後の空白を除き改行を保つ() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    use_case = ChangePatientHeadingUseCase(
        repository,
        _access(_actor(corporate_id)),
        FakeClock(_NOW),
    )

    dto = await use_case.execute(
        ChangePatientHeadingCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            expected_revision=0,
            provided_fields=frozenset({"summary", "notes"}),
            summary="  一行目  \r\n二行目  ",
            notes=" \t　",
        )
    )

    assert dto.summary == "一行目\n二行目"
    assert dto.notes is None


@pytest.mark.asyncio
async def test_tc43_17_正規化後に同値となる更新は保存しない() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = replace(
        create_patient(corporate_id=corporate_id),
        heading_history=(_revision("概要"),),
    )
    await repository.save(patient)
    save_count = repository.save_calls
    use_case = ChangePatientHeadingUseCase(
        repository, _access(_actor(corporate_id)), FakeClock(_NOW)
    )

    dto = await use_case.execute(
        ChangePatientHeadingCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            expected_revision=1,
            provided_fields=frozenset({"summary"}),
            summary=" 概要 ",
        )
    )

    assert dto.revision == 1
    assert dto.summary == "概要"
    assert repository.save_calls == save_count
    assert (
        await repository.get(corporate_id=corporate_id, patient_id=patient.id)
    ) == patient


@pytest.mark.asyncio
async def test_tc43_18_空の部分更新と不正改訂を保存前に拒否する() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    use_case = ChangePatientHeadingUseCase(
        repository, _access(_actor(corporate_id)), FakeClock(_NOW)
    )
    before = dict(repository.items)

    invalid_updates = [
        (-1, frozenset({"summary"}), None),
        (0, frozenset(), None),
        (0, frozenset({"summary"}), "あ" * 10_001),
        (0, frozenset({"notes"}), "あ" * 10_001),
    ]
    for revision, fields, _text in invalid_updates:
        with pytest.raises(DomainValidationError):
            await use_case.execute(
                ChangePatientHeadingCommand(
                    corporate_id=str(corporate_id.value),
                    patient_id=str(patient.id.value),
                    expected_revision=revision,
                    provided_fields=fields,
                    summary=_text if "summary" in fields else None,
                    notes=_text if "notes" in fields else None,
                )
            )

    assert repository.items == before


@pytest.mark.asyncio
async def test_tc43_19_記録者と時刻は本人と注入時計から得る() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    actor = _actor(corporate_id)
    clock = FakeClock(_NOW)
    await ChangePatientHeadingUseCase(repository, _access(actor), clock).execute(
        ChangePatientHeadingCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            expected_revision=0,
            provided_fields=frozenset({"summary"}),
            summary="薬剤師資格を持たない記録者でも利用できる",
        )
    )

    updated = await repository.get(corporate_id=corporate_id, patient_id=patient.id)
    assert updated is not None
    revision = updated.heading_history[-1]
    assert revision.person_id == actor.person_id
    assert revision.account_id == actor.account_id
    assert revision.recorded_at == _NOW


@pytest.mark.asyncio
async def test_tc43_20_本人未特定Actorは同値更新も拒否する() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    use_case = ChangePatientHeadingUseCase(
        repository,
        _access(ActorContext.vendor_system_admin(principal_id="未特定")),
        FakeClock(_NOW),
    )

    with pytest.raises(AuthorizationError):
        await use_case.execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                expected_revision=0,
                provided_fields=frozenset({"summary"}),
                summary=None,
            )
        )

    assert repository.items[patient.id].heading_history == ()


@pytest.mark.asyncio
async def test_tc43_22_頭書き権限は患者基本プロフィールの編集権限を与えない() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=corporate_id)
    await repository.save(patient)
    access = _access(_actor(corporate_id))
    clock = FakeClock(_NOW)
    await ChangePatientHeadingUseCase(repository, access, clock).execute(
        ChangePatientHeadingCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            expected_revision=0,
            provided_fields=frozenset({"summary"}),
            summary="頭書きだけを更新",
        )
    )

    with pytest.raises(AuthorizationError):
        await ChangePatientNamesUseCase(repository, access, clock).execute(
            ChangePatientNamesCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                last_name="変更",
                first_name="不可",
                last_name_kana="ヘンコウ",
                first_name_kana="フカ",
            )
        )
    with pytest.raises(AuthorizationError):
        await ChangePatientProfileUseCase(repository, access, clock).execute(
            ChangePatientProfileCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                provided_fields=frozenset({"address"}),
                address="基本プロフィールの更新は許可しない",
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        ActorRole.CORPORATE_ADMIN,
        ActorRole.STORE_OPERATOR,
        ActorRole.STORE_VIEWER,
    ],
)
async def test_tc43_23_別法人の患者と存在を隠す(role: ActorRole) -> None:
    corporate_id = CorporateId.generate()
    other_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    patient = create_patient(corporate_id=other_id)
    await repository.save(patient)
    access = _access(_actor(corporate_id, role))
    use_case = GetPatientHeadingUseCase(repository, access)

    with pytest.raises((TenantBoundaryNotFoundError, PatientNotFoundError)):
        await use_case.execute(
            GetPatientHeadingQuery(
                corporate_id=str(corporate_id.value), patient_id=str(patient.id.value)
            )
        )
    with pytest.raises((TenantBoundaryNotFoundError, PatientNotFoundError)):
        await ChangePatientHeadingUseCase(repository, access, FakeClock(_NOW)).execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                expected_revision=0,
                provided_fields=frozenset({"summary"}),
                summary="別法人患者へ届かない",
            )
        )
    assert patient.id in repository.items
    assert repository.items[patient.id].heading_history == ()


@pytest.mark.asyncio
async def test_tc43_24_存在しない患者は頭書きを作らない() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryPatientRepository()
    use_case = GetPatientHeadingUseCase(repository, _access(_actor(corporate_id)))

    patient_id = PatientId.generate()
    with pytest.raises(PatientNotFoundError):
        await use_case.execute(
            GetPatientHeadingQuery(
                corporate_id=str(corporate_id.value), patient_id=str(patient_id.value)
            )
        )
    with pytest.raises(PatientNotFoundError):
        await ChangePatientHeadingUseCase(
            repository, _access(_actor(corporate_id)), FakeClock(_NOW)
        ).execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient_id.value),
                expected_revision=0,
                provided_fields=frozenset({"summary"}),
                summary="存在しない患者",
            )
        )

    assert repository.items == {}


@pytest.mark.asyncio
async def test_tc43_25_無効法人の患者頭書きを参照できない() -> None:
    corporate_id = CorporateId.generate()
    corporates = AutoProvisioningCorporateRepository()
    corporates.set_inactive(corporate_id)
    patient = create_patient(corporate_id=corporate_id)
    repository = InMemoryPatientRepository()
    await repository.save(patient)
    access = CorporateAccessService(
        corporates, AuthorizationService(_actor(corporate_id))
    )

    with pytest.raises(CorporateInactiveError):
        await GetPatientHeadingUseCase(repository, access).execute(
            GetPatientHeadingQuery(
                corporate_id=str(corporate_id.value), patient_id=str(patient.id.value)
            )
        )
    with pytest.raises(CorporateInactiveError):
        await ChangePatientHeadingUseCase(repository, access, FakeClock(_NOW)).execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                expected_revision=0,
                provided_fields=frozenset({"summary"}),
                summary="停止中法人では更新しない",
            )
        )
    assert repository.items[patient.id].heading_history == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "can_update"),
    [
        (PatientStatus.ACTIVE, True),
        (PatientStatus.INACTIVE, True),
        (PatientStatus.MERGED, False),
    ],
    ids=["有効", "無効", "統合済み"],
)
async def test_tc43_26_患者状態に応じて頭書きを参照し更新する(
    status: PatientStatus, can_update: bool
) -> None:
    corporate_id = CorporateId.generate()
    patient = create_patient(corporate_id=corporate_id)
    if status is PatientStatus.MERGED:
        patient = replace(patient, status=status, merged_into_id=PatientId.generate())
    else:
        patient = replace(patient, status=status)
    repository = InMemoryPatientRepository()
    await repository.save(patient)
    access = _access(_actor(corporate_id))
    read = await GetPatientHeadingUseCase(repository, access).execute(
        GetPatientHeadingQuery(
            corporate_id=str(corporate_id.value), patient_id=str(patient.id.value)
        )
    )
    assert read.revision == 0
    assert read.history == ()

    update = ChangePatientHeadingUseCase(repository, access, FakeClock(_NOW))
    if can_update:
        dto = await update.execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                expected_revision=0,
                provided_fields=frozenset({"notes"}),
                notes="有効状態に応じた申し送り",
            )
        )
        assert dto.notes == "有効状態に応じた申し送り"
    else:
        with pytest.raises(PatientStateConflictError):
            await update.execute(
                ChangePatientHeadingCommand(
                    corporate_id=str(corporate_id.value),
                    patient_id=str(patient.id.value),
                    expected_revision=0,
                    provided_fields=frozenset({"notes"}),
                    notes="統合済み患者の更新",
                )
            )


@pytest.mark.asyncio
async def test_tc43_27_画面表示後の古い改訂は更新しない() -> None:
    corporate_id = CorporateId.generate()
    patient = replace(
        create_patient(corporate_id=corporate_id),
        heading_history=(_revision("先行更新"),),
    )
    repository = InMemoryPatientRepository()
    await repository.save(patient)
    use_case = ChangePatientHeadingUseCase(
        repository, _access(_actor(corporate_id)), FakeClock(_NOW)
    )

    with pytest.raises(PatientHeadingConflictError):
        await use_case.execute(
            ChangePatientHeadingCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                expected_revision=0,
                provided_fields=frozenset({"summary"}),
                summary="古い画面からの内容",
            )
        )

    assert repository.items[patient.id].heading_history == patient.heading_history
