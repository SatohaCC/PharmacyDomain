"""患者一覧・検索ユースケースのテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.errors import StoreContextRequiredError
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.patient.queries.list_patients import ListPatientsUseCase
from app.application.patient.queries.models import ListPatientsQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import Patient
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import (
    PatientBirthDate,
    PatientNumber,
    PatientPhoneNumber,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.patient_list_patients import ListPatientsProjection
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository


def _create_actor(
    corporate_id: CorporateId,
    roles: set[ActorRole] | None = None,
) -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="test-operator",
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        roles=frozenset(roles or {ActorRole.CORPORATE_ADMIN}),
        corporate_id=corporate_id,
    )


def _make_patient(
    *,
    corporate_id: CorporateId,
    patient_number: int,
    last_name: str,
    first_name: str,
    last_name_kana: str,
    first_name_kana: str,
    phone: str | None = None,
) -> Patient:
    return Patient(
        id=PatientId.generate(),
        corporate_id=corporate_id,
        patient_number=PatientNumber(patient_number),
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart(last_name),
                first_name=PersonNamePart(first_name),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart(last_name_kana),
                first_name=PersonNameKanaPart(first_name_kana),
            ),
        ),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
        phone_number=PatientPhoneNumber(phone) if phone else None,
    )


@pytest.mark.anyio
async def test_患者一覧_自法人の患者全件取得_患者番号順で取得できる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    other_corporate_id = CorporateId.generate()
    corp_repo = AutoProvisioningCorporateRepository()
    patient_repo = InMemoryPatientRepository()
    actor = _create_actor(corporate_id)
    access = CorporateAccessService(corp_repo, AuthorizationService(actor))

    p1 = _make_patient(
        corporate_id=corporate_id,
        patient_number=1,
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
    )
    p2 = _make_patient(
        corporate_id=corporate_id,
        patient_number=2,
        last_name="鈴木",
        first_name="花子",
        last_name_kana="スズキ",
        first_name_kana="ハナコ",
    )
    other_p = _make_patient(
        corporate_id=other_corporate_id,
        patient_number=1,
        last_name="他社",
        first_name="患者",
        last_name_kana="タシャ",
        first_name_kana="カンジャ",
    )
    await patient_repo.save(p2)
    await patient_repo.save(p1)
    await patient_repo.save(other_p)

    use_case = ListPatientsUseCase(
        reader=ListPatientsProjection(patient_repo),
        corporate_access=access,
    )

    # Act
    results = await use_case.execute(
        ListPatientsQuery(corporate_id=str(corporate_id.value))
    )

    # Assert
    assert len(results) == 2
    assert results[0].patient_number == 1
    assert results[0].last_name == "山田"
    assert results[1].patient_number == 2
    assert results[1].last_name == "鈴木"


@pytest.mark.anyio
async def test_患者一覧_キーワード検索_カナまたは漢字氏名で一致する患者のみ取得できる() -> (
    None
):
    # Arrange
    corporate_id = CorporateId.generate()
    corp_repo = AutoProvisioningCorporateRepository()
    patient_repo = InMemoryPatientRepository()
    actor = _create_actor(corporate_id)
    access = CorporateAccessService(corp_repo, AuthorizationService(actor))

    p1 = _make_patient(
        corporate_id=corporate_id,
        patient_number=1,
        last_name="佐藤",
        first_name="健太",
        last_name_kana="サトウ",
        first_name_kana="ケンタ",
    )
    p2 = _make_patient(
        corporate_id=corporate_id,
        patient_number=2,
        last_name="田中",
        first_name="美咲",
        last_name_kana="タナカ",
        first_name_kana="ミサキ",
    )
    await patient_repo.save(p1)
    await patient_repo.save(p2)

    use_case = ListPatientsUseCase(
        reader=ListPatientsProjection(patient_repo),
        corporate_access=access,
    )

    # Act & Assert
    results_kanji = await use_case.execute(
        ListPatientsQuery(corporate_id=str(corporate_id.value), keyword="佐藤")
    )
    assert len(results_kanji) == 1
    assert results_kanji[0].last_name == "佐藤"

    results_kana = await use_case.execute(
        ListPatientsQuery(corporate_id=str(corporate_id.value), keyword="ミサキ")
    )
    assert len(results_kana) == 1
    assert results_kana[0].first_name == "美咲"

    results_number = await use_case.execute(
        ListPatientsQuery(corporate_id=str(corporate_id.value), keyword="1")
    )
    assert len(results_number) == 1
    assert results_number[0].patient_number == 1


@pytest.mark.anyio
async def test_患者一覧_権限なし_認可エラーになる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    corp_repo = AutoProvisioningCorporateRepository()
    patient_repo = InMemoryPatientRepository()
    actor = _create_actor(corporate_id, roles={ActorRole.MEMBER})
    access = CorporateAccessService(corp_repo, AuthorizationService(actor))

    use_case = ListPatientsUseCase(
        reader=ListPatientsProjection(patient_repo),
        corporate_access=access,
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        await use_case.execute(ListPatientsQuery(corporate_id=str(corporate_id.value)))


@pytest.mark.anyio
@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
async def test_患者一覧_店舗スタッフ_店舗選択済み_参照できる(role: ActorRole) -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    corp_repo = AutoProvisioningCorporateRepository()
    patient_repo = InMemoryPatientRepository()
    actor = ResolvedActorContext(
        principal_id="test-store-operator",
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        roles=frozenset({role}),
        corporate_id=corporate_id,
        store_ids=frozenset({store_id}),
        selected_store_id=store_id,
        require_store_selection=True,
    )
    access = CorporateAccessService(corp_repo, AuthorizationService(actor))

    p = _make_patient(
        corporate_id=corporate_id,
        patient_number=1,
        last_name="山田",
        first_name="太郎",
        last_name_kana="ヤマダ",
        first_name_kana="タロウ",
    )
    await patient_repo.save(p)

    use_case = ListPatientsUseCase(
        reader=ListPatientsProjection(patient_repo),
        corporate_access=access,
    )

    # Act
    results = await use_case.execute(
        ListPatientsQuery(corporate_id=str(corporate_id.value))
    )

    # Assert
    assert len(results) == 1
    assert results[0].last_name == "山田"


@pytest.mark.anyio
async def test_患者一覧_店舗スタッフ_店舗未選択_StoreContextRequiredError() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    corp_repo = AutoProvisioningCorporateRepository()
    patient_repo = InMemoryPatientRepository()
    actor = ResolvedActorContext(
        principal_id="test-store-operator",
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        corporate_id=corporate_id,
        store_ids=frozenset({store_id}),
        selected_store_id=None,
        require_store_selection=True,
    )
    access = CorporateAccessService(corp_repo, AuthorizationService(actor))

    use_case = ListPatientsUseCase(
        reader=ListPatientsProjection(patient_repo),
        corporate_access=access,
    )

    # Act & Assert
    with pytest.raises(StoreContextRequiredError):
        await use_case.execute(ListPatientsQuery(corporate_id=str(corporate_id.value)))
