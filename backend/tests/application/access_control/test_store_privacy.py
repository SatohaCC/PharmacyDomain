"""店舗ロールへ法人共通の情報を公開しない。"""

from dataclasses import asdict, replace
from datetime import date

import pytest

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.medication_history.queries.get_patient_medical_profile import (
    GetPatientMedicalProfileUseCase,
)
from app.application.medication_history.queries.models import (
    GetPatientMedicalProfileQuery,
)
from app.application.staff.queries.get_staff import GetStaffUseCase
from app.application.staff.queries.models import GetStaffQuery
from app.domain.patient.identifiers import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.primitives import StaffEmailAddress, StaffPhoneNumber
from app.infrastructure.readers.medication_history_get_patient_medical_profile import (
    GetPatientMedicalProfileProjection,
)
from app.infrastructure.readers.staff_get_staff import GetStaffProjection
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.factories.staff_factory import create_staff
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_patient_medical_profile_repository import (
    InMemoryPatientMedicalProfileRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("check_profile", [False, True])
@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
async def test_店舗ロールのスタッフ詳細に個人連絡先を含めず頭書きを拒否する(
    role: ActorRole, check_profile: bool
) -> None:
    staff = replace(
        create_staff(),
        phone_number=StaffPhoneNumber("0312345678"),
        email=StaffEmailAddress("private@example.test"),
    )
    repository = InMemoryStaffRepository()
    await repository.save(staff)
    actor = ResolvedActorContext(
        principal_id="本人",
        roles=frozenset({role}),
        corporate_id=staff.corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )
    result = await GetStaffUseCase(
        reader=GetStaffProjection(repository),
        corporate_access=access,
        clock=FakeClock(),
    ).execute(
        GetStaffQuery(
            corporate_id=str(staff.corporate_id.value), staff_id=str(staff.id.value)
        )
    )
    if not check_profile:
        assert "phone_number" not in asdict(result)
        assert "email" not in asdict(result)
        return
    use_case = GetPatientMedicalProfileUseCase(
        reader=GetPatientMedicalProfileProjection(
            InMemoryPatientMedicalProfileRepository()
        ),
        corporate_access=access,
    )
    with pytest.raises(AuthorizationError):
        await use_case.execute(
            GetPatientMedicalProfileQuery(
                corporate_id=str(staff.corporate_id.value),
                patient_id=str(PatientId.generate().value),
                as_of=date(2026, 9, 17),
            )
        )
