"""外部患者ID登録ユースケースのテスト。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.common.exceptions import ApplicationError
from app.application.patient.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierCommand,
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierCommand,
    RegisterPatientExternalIdentifierUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.patient import Patient
from app.domain.shared.person_name import PersonNames
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_patient_repository import (
    InMemoryPatientExternalIdentifierRepository,
    InMemoryPatientRepository,
)
from tests.fakes.in_memory_patient_store_reference import (
    InMemoryPatientStoreReference,
)
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

_SYSTEM_NAME = "RECEIPT_A"
_EXTERNAL_ID = "X1"


async def _create_patient(
    repository: InMemoryPatientRepository,
    *,
    corporate_id: CorporateId,
    last_name: str = "山田",
    last_name_kana: str = "ヤマダ",
) -> Patient:
    """テスト用の患者を保存して返す。"""
    patient = Patient.create(
        corporate_id=corporate_id,
        names=PersonNames.create(
            last_name=last_name,
            first_name="太郎",
            last_name_kana=last_name_kana,
            first_name_kana="タロウ",
        ),
        patient_number=await repository.allocate_patient_number(corporate_id),
    )
    await repository.save(patient)
    return patient


def _create_use_cases(
    store_repository: InMemoryStoreRepository | None = None,
) -> tuple[
    RegisterPatientExternalIdentifierUseCase,
    DeactivatePatientExternalIdentifierUseCase,
    InMemoryPatientRepository,
    InMemoryPatientExternalIdentifierRepository,
]:
    """登録・無効化ユースケースと患者Repositoryを組み立てる。"""
    patient_repository = InMemoryPatientRepository()
    identifier_repository = InMemoryPatientExternalIdentifierRepository()
    register = RegisterPatientExternalIdentifierUseCase(
        patient_repository,
        identifier_repository,
        create_vendor_corporate_access(),
        store_reference=(
            InMemoryPatientStoreReference(store_repository)
            if store_repository is not None
            else None
        ),
    )
    deactivate = DeactivatePatientExternalIdentifierUseCase(
        identifier_repository,
        create_vendor_corporate_access(),
    )
    return register, deactivate, patient_repository, identifier_repository


@pytest.mark.asyncio
async def test_外部患者ID登録_有効な対応付けが既にあると_重複エラーになる() -> None:
    # Arrange
    register, _, patient_repository, _ = _create_use_cases()
    corporate_id = CorporateId.generate()
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)
    command = RegisterPatientExternalIdentifierCommand(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
        system_name=_SYSTEM_NAME,
        external_patient_id=_EXTERNAL_ID,
        store_id=str(StoreId.generate().value),
    )
    await register.execute(command)

    # Act / Assert
    with pytest.raises(PatientExternalIdentifierAlreadyExistsError):
        await register.execute(command)


@pytest.mark.asyncio
async def test_外部患者ID登録_無効化後は同じ外部IDを_再登録できる() -> None:
    # Arrange
    register, deactivate, patient_repository, _ = _create_use_cases()
    corporate_id = CorporateId.generate()
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)
    command = RegisterPatientExternalIdentifierCommand(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
        system_name=_SYSTEM_NAME,
        external_patient_id=_EXTERNAL_ID,
        store_id=str(StoreId.generate().value),
    )
    registered = await register.execute(command)
    await deactivate.execute(
        DeactivatePatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            identifier_id=registered.id,
        )
    )

    # Act
    actual = await register.execute(command)

    # Assert
    assert (actual.external_patient_id, actual.is_active) == (_EXTERNAL_ID, True)


@pytest.mark.asyncio
async def test_外部患者ID登録_誤紐付けを無効化すると_正しい患者へ付け替えられる() -> (
    None
):
    # Arrange
    register, deactivate, patient_repository, _ = _create_use_cases()
    corporate_id = CorporateId.generate()
    wrong_patient = await _create_patient(
        patient_repository,
        corporate_id=corporate_id,
        last_name="佐藤",
        last_name_kana="サトウ",
    )
    correct_patient = await _create_patient(
        patient_repository,
        corporate_id=corporate_id,
        last_name="鈴木",
        last_name_kana="スズキ",
    )
    store_id = StoreId.generate()
    mis_linked = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(wrong_patient.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id=_EXTERNAL_ID,
            store_id=str(store_id.value),
        )
    )
    await deactivate.execute(
        DeactivatePatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            identifier_id=mis_linked.id,
        )
    )

    # Act
    actual = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(correct_patient.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id=_EXTERNAL_ID,
            store_id=str(store_id.value),
        )
    )

    # Assert
    assert actual.patient_id == str(correct_patient.id.value)


@pytest.mark.asyncio
async def test_tc60_同じ外部IDを異なる店舗の別患者へ登録できる() -> None:
    """店舗別レセコンで同じID文字列が別患者を示すことを許す。"""
    store_repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store_a = StoreId.generate()
    store_b = StoreId.generate()
    await store_repository.save(
        replace(
            create_store(corporate_id=corporate_id, name="店舗A"),
            id=store_a,
        )
    )
    await store_repository.save(
        replace(
            create_store(corporate_id=corporate_id, name="店舗B"),
            id=store_b,
        )
    )
    register, _, patient_repository, identifier_repository = _create_use_cases(
        store_repository
    )
    patient_a = await _create_patient(patient_repository, corporate_id=corporate_id)
    patient_b = await _create_patient(
        patient_repository,
        corporate_id=corporate_id,
        last_name="佐藤",
        last_name_kana="サトウ",
    )

    linked_a = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient_a.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id=_EXTERNAL_ID,
            store_id=str(store_a.value),
        )
    )
    linked_b = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient_b.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id=_EXTERNAL_ID,
            store_id=str(store_b.value),
        )
    )

    assert linked_a.patient_id == str(patient_a.id.value)
    assert linked_b.patient_id == str(patient_b.id.value)
    assert {item.store_id for item in identifier_repository.items.values()} == {
        store_a,
        store_b,
    }


@pytest.mark.asyncio
async def test_tc61_複数店舗の患者IDを同じPatientへ登録できる() -> None:
    """店舗別レセコンIDを一つの薬歴患者へ対応付けられる。"""
    store_repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store_a = StoreId.generate()
    store_b = StoreId.generate()
    await store_repository.save(
        replace(
            create_store(corporate_id=corporate_id, name="店舗A"),
            id=store_a,
        )
    )
    await store_repository.save(
        replace(
            create_store(corporate_id=corporate_id, name="店舗B"),
            id=store_b,
        )
    )
    register, _, patient_repository, identifier_repository = _create_use_cases(
        store_repository
    )
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)

    linked_a = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id="STORE-A-42",
            store_id=str(store_a.value),
        )
    )
    linked_b = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(patient.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id="STORE-B-73",
            store_id=str(store_b.value),
        )
    )

    assert linked_a.patient_id == linked_b.patient_id == str(patient.id.value)
    patient_links = await identifier_repository.list_by_patient(
        corporate_id=corporate_id,
        patient_id=patient.id,
    )
    assert len(patient_links) == 2
    assert {item.store_id for item in patient_links} == {store_a, store_b}


@pytest.mark.asyncio
@pytest.mark.parametrize("store_kind", ("missing", "other_corporate"))
async def test_tc63_法人外または存在しない店舗の患者ID登録は書き込まない(
    store_kind: str,
) -> None:
    """店舗スコープを持つ外部IDは同じ法人に存在する店舗だけへ登録できる。"""
    store_repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    register, _, patient_repository, identifier_repository = _create_use_cases(
        store_repository
    )
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)
    store_id = StoreId.generate()
    if store_kind == "other_corporate":
        foreign_store = replace(
            create_store(corporate_id=CorporateId.generate()),
            id=store_id,
        )
        await store_repository.save(foreign_store)

    with pytest.raises(ApplicationError):
        await register.execute(
            RegisterPatientExternalIdentifierCommand(
                corporate_id=str(corporate_id.value),
                patient_id=str(patient.id.value),
                system_name=_SYSTEM_NAME,
                external_patient_id=_EXTERNAL_ID,
                store_id=str(store_id.value),
            )
        )

    assert identifier_repository.items == {}
