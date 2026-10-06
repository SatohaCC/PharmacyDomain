from __future__ import annotations

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusCommand,
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId, CorporateStatus
from tests.application.corporate.helpers import save_corporate
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


class ロック確認Repository(InMemoryCorporateRepository):
    """状態変更が法人を読み出す前にロックを取得することを確認する。"""

    def __init__(self, lock: FakeOrganizationLock) -> None:
        super().__init__()
        self._lock = lock

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        assert self._lock.keys == [f"corporate:{corporate_id.value}"]
        return await super().get(corporate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_active", [True, False])
@pytest.mark.parametrize("target_active", [True, False])
async def test_法人状態変更_停止と再開と同じ状態の指定_読み出し前に法人ロックを取得する(
    initial_active: bool, target_active: bool
) -> None:
    # Arrange
    lock = FakeOrganizationLock()
    repository = ロック確認Repository(lock)
    corporate = await save_corporate(repository)
    if not initial_active:
        await repository.save(corporate.deactivate())
    access = CorporateAccessService(
        repository,
        AuthorizationService(ActorContext.vendor_system_admin(principal_id="vendor")),
    )
    use_case = ChangeCorporateStatusUseCase(repository, access, lock)

    # Act
    await use_case.execute(
        ChangeCorporateStatusCommand(
            corporate_id=str(corporate.id.value), is_active=target_active
        )
    )

    # Assert
    actual = await repository.get(corporate.id)
    assert actual is not None
    assert actual.is_active is target_active


@pytest.mark.asyncio
async def test_change_corporate_status_vendor_admin_deactivate_changes_status_to_inactive() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
        ),
    )
    use_case = ChangeCorporateStatusUseCase(repository, access, FakeOrganizationLock())

    # Act
    await use_case.execute(
        ChangeCorporateStatusCommand(
            corporate_id=str(corporate.id.value),
            is_active=False,
        )
    )

    # Assert
    inactive = await repository.get(corporate.id)
    assert inactive is not None
    assert inactive.status is CorporateStatus.INACTIVE


@pytest.mark.asyncio
async def test_change_corporate_status_vendor_admin_reactivate_changes_status_to_active() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    await repository.save(corporate.deactivate())
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
        ),
    )
    use_case = ChangeCorporateStatusUseCase(repository, access, FakeOrganizationLock())

    # Act
    await use_case.execute(
        ChangeCorporateStatusCommand(
            corporate_id=str(corporate.id.value),
            is_active=True,
        )
    )

    # Assert
    active = await repository.get(corporate.id)
    assert active is not None
    assert active.status is CorporateStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_corporate_inactive_corporate_returns_dto_with_is_active_false() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    await repository.save(corporate.deactivate())
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="vendor-admin-1")
        ),
    )

    # Act
    actual = await GetCorporateUseCase(access).execute(str(corporate.id.value))

    # Assert
    assert actual.is_active is False


@pytest.mark.asyncio
async def test_change_corporate_status_corporate_admin_raises_authorization_error() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=corporate.id,
            )
        ),
    )
    lock = FakeOrganizationLock()
    use_case = ChangeCorporateStatusUseCase(repository, access, lock)

    # Act & Assert
    with pytest.raises(AuthorizationError):
        await use_case.execute(
            ChangeCorporateStatusCommand(
                corporate_id=str(corporate.id.value),
                is_active=False,
            )
        )
    assert lock.keys == []


@pytest.mark.asyncio
async def test_法人状態変更_他法人の管理者_ロックを取得せず存在を隠す() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    lock = FakeOrganizationLock()
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="foreign-admin", corporate_id=CorporateId.generate()
            )
        ),
    )
    use_case = ChangeCorporateStatusUseCase(repository, access, lock)

    # Act / Assert
    with pytest.raises(TenantBoundaryNotFoundError):
        await use_case.execute(
            ChangeCorporateStatusCommand(
                corporate_id=str(corporate.id.value), is_active=False
            )
        )
    assert lock.keys == []
    actual = await repository.get(corporate.id)
    assert actual is not None
    assert actual.is_active
