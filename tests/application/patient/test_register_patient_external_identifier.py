"""外部患者ID登録ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.patient.deactivate_patient_external_identifier import (
    DeactivatePatientExternalIdentifierCommand,
    DeactivatePatientExternalIdentifierUseCase,
)
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierCommand,
    RegisterPatientExternalIdentifierUseCase,
)
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.patient import Patient
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.in_memory_patient_repository import (
    InMemoryPatientExternalIdentifierRepository,
    InMemoryPatientRepository,
)

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


def _create_use_cases() -> tuple[
    RegisterPatientExternalIdentifierUseCase,
    DeactivatePatientExternalIdentifierUseCase,
    InMemoryPatientRepository,
]:
    """登録・無効化ユースケースと患者Repositoryを組み立てる。"""
    patient_repository = InMemoryPatientRepository()
    identifier_repository = InMemoryPatientExternalIdentifierRepository()
    register = RegisterPatientExternalIdentifierUseCase(
        patient_repository,
        identifier_repository,
        create_vendor_corporate_access(),
    )
    deactivate = DeactivatePatientExternalIdentifierUseCase(
        identifier_repository,
        create_vendor_corporate_access(),
    )
    return register, deactivate, patient_repository


@pytest.mark.asyncio
async def test_外部患者ID登録_有効な対応付けが既にあると_重複エラーになる() -> None:
    # Arrange
    register, _, patient_repository = _create_use_cases()
    corporate_id = CorporateId.generate()
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)
    command = RegisterPatientExternalIdentifierCommand(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
        system_name=_SYSTEM_NAME,
        external_patient_id=_EXTERNAL_ID,
    )
    await register.execute(command)

    # Act / Assert
    with pytest.raises(PatientExternalIdentifierAlreadyExistsError):
        await register.execute(command)


@pytest.mark.asyncio
async def test_外部患者ID登録_無効化後は同じ外部IDを_再登録できる() -> None:
    # Arrange
    register, deactivate, patient_repository = _create_use_cases()
    corporate_id = CorporateId.generate()
    patient = await _create_patient(patient_repository, corporate_id=corporate_id)
    command = RegisterPatientExternalIdentifierCommand(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
        system_name=_SYSTEM_NAME,
        external_patient_id=_EXTERNAL_ID,
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
    register, deactivate, patient_repository = _create_use_cases()
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
    mis_linked = await register.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=str(corporate_id.value),
            patient_id=str(wrong_patient.id.value),
            system_name=_SYSTEM_NAME,
            external_patient_id=_EXTERNAL_ID,
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
        )
    )

    # Assert
    assert actual.patient_id == str(correct_patient.id.value)
