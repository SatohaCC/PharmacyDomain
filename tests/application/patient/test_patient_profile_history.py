"""患者プロフィール受信履歴の参照契約テスト。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

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
from app.application.patient.get_patient import GetPatientQuery, GetPatientUseCase
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.patient.primitives import (
    ExternalPatientId,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.persistence_factory import create_patient
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository


def _corporate_access(actor: ActorContext) -> CorporateAccessService:
    """指定Actorを使う患者詳細閲覧境界を組み立てる。"""
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(),
        AuthorizationService(actor),
    )


def _profile_change() -> PatientProfileChange:
    """履歴DTO変換に使う受信プロフィールを作る。"""
    patient = create_patient()
    return PatientProfileChange(
        reception_id=ReceptionId.generate(),
        store_id=StoreId.generate(),
        external_patient_id=ExternalPatientId("RECEIPT-42"),
        recorded_at=datetime(2026, 9, 23, 1, 2, 3, tzinfo=UTC),
        changed_fields=("patient.address",),
        received_profile=PatientProfileSnapshot(
            names=patient.names,
            birth_date=PatientBirthDate(date(1980, 1, 2)),
            gender=PatientGenderCode("1"),
            postal_code=PatientPostalCode("1000001"),
            address=PatientAddress("東京都千代田区"),
            phone_number=PatientPhoneNumber("03-0000-0000"),
        ),
    )


@pytest.mark.asyncio
async def test_tc70_認可された患者詳細DTOにプロフィール受信履歴を含める() -> None:
    """既存の患者詳細認可境界の内側で受信履歴を型付きDTOとして返す。"""
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = replace(
        create_patient(corporate_id=corporate_id), profile_history=(_profile_change(),)
    )
    await repository.save(patient)

    query = GetPatientQuery(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
    )
    authorized = GetPatientUseCase(
        repository,
        _corporate_access(ActorContext.vendor_system_admin(principal_id="authorized")),
    )

    dto = await authorized.execute(query)

    assert len(dto.profile_history) == 1
    change = dto.profile_history[0]
    assert change.changed_fields == ("patient.address",)
    assert change.received_profile.address == "東京都千代田区"
    assert change.received_profile.postal_code == "1000001"
    assert change.received_profile.phone_number == "03-0000-0000"
    assert change.external_patient_id == "RECEIPT-42"


@pytest.mark.asyncio
async def test_tc70_患者プロフィール履歴は閲覧権限と法人境界の内側にある() -> None:
    """履歴の詳細はVIEW_PATIENTなしや他法人のActorへ返さない。"""
    repository = InMemoryPatientRepository()
    corporate_id = CorporateId.generate()
    patient = replace(
        create_patient(corporate_id=corporate_id), profile_history=(_profile_change(),)
    )
    await repository.save(patient)
    query = GetPatientQuery(
        corporate_id=str(corporate_id.value),
        patient_id=str(patient.id.value),
    )

    viewer = ResolvedActorContext(
        principal_id="store-viewer",
        roles=frozenset({ActorRole.STORE_VIEWER}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        store_ids=frozenset({StoreId.generate()}),
    )
    with pytest.raises(AuthorizationError):
        await GetPatientUseCase(repository, _corporate_access(viewer)).execute(query)

    other_corporate = CorporateId.generate()
    other_admin = ActorContext(
        principal_id="other-corporate-admin",
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        corporate_id=other_corporate,
    )
    with pytest.raises(TenantBoundaryNotFoundError):
        await GetPatientUseCase(
            repository,
            _corporate_access(other_admin),
        ).execute(query)
