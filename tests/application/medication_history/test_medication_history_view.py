"""薬歴本文と患者の現行プロフィールを合わせて読む契約テスト。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorContext, Permission
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_medication_history import (
    GetMedicationHistoryQuery,
)
from app.application.medication_history.get_medication_history_view import (
    CurrentPatientProfileBoundary,
    GetMedicationHistoryViewQuery,
    GetMedicationHistoryViewUseCase,
    MedicationHistoryPatientProfileDto,
)
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_start_command,
)


@dataclass
class _CurrentPatientProfileReader(CurrentPatientProfileBoundary):
    """読取時点プロフィールを返す境界Fake。"""

    profile: MedicationHistoryPatientProfileDto
    requested: tuple[CorporateId, PatientId] | None = None

    async def get_current_profile(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> MedicationHistoryPatientProfileDto | None:
        """要求された患者を記録して現行プロフィールを返す。"""
        self.requested = (corporate_id, patient_id)
        return self.profile


class _PermissionLimitedCorporateAccess(CorporateAccessBoundary):
    """指定権限だけを拒否する認可Boundary。"""

    def __init__(self, denied: Permission) -> None:
        self._denied = denied
        self._delegate = CorporateAccessService(
            AutoProvisioningCorporateRepository(),
            AuthorizationService(ActorContext.vendor_system_admin(principal_id="test")),
        )
        self.requested_permissions: list[Permission] = []

    @property
    def actor(self) -> ActorContext:
        """テスト用認可主体を返す。"""
        return self._delegate.actor

    async def require_active(
        self,
        *,
        corporate_id: CorporateId,
        permission: Permission,
    ) -> Corporate:
        """要求権限を記録し、指定された権限だけ拒否する。"""
        self.requested_permissions.append(permission)
        if permission == self._denied:
            raise AuthorizationError(f"{permission.value} がありません。")
        return await self._delegate.require_active(
            corporate_id=corporate_id,
            permission=permission,
        )


def _profile(address: str) -> MedicationHistoryPatientProfileDto:
    """読取時点の患者プロフィールを組み立てる。"""
    return MedicationHistoryPatientProfileDto(
        last_name="山田",
        first_name="花子",
        last_name_kana="ヤマダ",
        first_name_kana="ハナコ",
        birth_date="1980-01-02",
        gender="2",
        postal_code="1000001",
        address=address,
        phone_number="03-0000-0000",
    )


async def _finalized_record(fixture: MedicationHistoryFixture) -> str:
    """薬歴を作成・確定して、そのIDを返す。"""
    started = await fixture.start.execute(create_start_command(fixture))
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    return started.id


def _view_use_case(
    fixture: MedicationHistoryFixture,
    profile_reader: CurrentPatientProfileBoundary,
    access: CorporateAccessBoundary | None = None,
) -> GetMedicationHistoryViewUseCase:
    """実Repository・認可境界とプロフィールFakeから読取UseCaseを作る。"""
    corporate_access = access or CorporateAccessService(
        fixture.corporate_repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="view-reader")
        ),
    )
    return GetMedicationHistoryViewUseCase(
        fixture.record_repository,
        profile_reader,
        corporate_access,
    )


@pytest.mark.asyncio
async def test_tc82_確定薬歴本文を変えず読取時点の患者住所を返す() -> None:
    """住所変更後の薬歴表示は保存本文と読取時プロフィールを分けて返す。"""
    fixture = create_fixture()
    record_id = await _finalized_record(fixture)
    saved_record = await fixture.get.execute(
        GetMedicationHistoryQuery(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
        )
    )
    reader = _CurrentPatientProfileReader(_profile("東京都中央区二丁目"))
    use_case = _view_use_case(fixture, reader)

    view = await use_case.execute(
        GetMedicationHistoryViewQuery(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
        )
    )

    assert view.record == saved_record
    assert view.current_patient_profile.address == "東京都中央区二丁目"
    assert reader.requested == (fixture.corporate_id, fixture.patient_id)
    after_read = await fixture.get.execute(
        GetMedicationHistoryQuery(
            corporate_id=str(fixture.corporate_id.value),
            record_id=record_id,
        )
    )
    assert after_read == saved_record
    assert view.record.soap == saved_record.soap


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "denied_permission",
    (Permission.VIEW_PATIENT, Permission.VIEW_MEDICATION_HISTORY),
)
async def test_tc83_薬歴と患者の両閲覧権限が必要(
    denied_permission: Permission,
) -> None:
    """片方の閲覧権限がない場合はプロフィールBoundaryを呼ばない。"""
    fixture = create_fixture()
    record_id = await _finalized_record(fixture)
    reader = _CurrentPatientProfileReader(_profile("東京都千代田区"))
    access = _PermissionLimitedCorporateAccess(denied_permission)
    use_case = _view_use_case(fixture, reader, access)

    with pytest.raises(AuthorizationError):
        await use_case.execute(
            GetMedicationHistoryViewQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
            )
        )

    assert denied_permission in access.requested_permissions
    assert reader.requested is None


@pytest.mark.asyncio
async def test_tc83_他法人の薬歴表示は404境界で隠す() -> None:
    """他法人Actorには患者プロフィールを読ませず存在を隠す。"""
    fixture = create_fixture()
    record_id = await _finalized_record(fixture)
    reader = _CurrentPatientProfileReader(_profile("秘匿住所"))
    other_corporate_id = CorporateId.generate()
    actor = ActorContext.corporate_admin(
        principal_id="other-corporate",
        corporate_id=other_corporate_id,
    )
    access = CorporateAccessService(
        fixture.corporate_repository,
        AuthorizationService(actor),
    )
    use_case = _view_use_case(fixture, reader, access)

    with pytest.raises(TenantBoundaryNotFoundError):
        await use_case.execute(
            GetMedicationHistoryViewQuery(
                corporate_id=str(fixture.corporate_id.value),
                record_id=record_id,
            )
        )

    assert reader.requested is None
