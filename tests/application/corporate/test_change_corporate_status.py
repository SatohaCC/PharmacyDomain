from __future__ import annotations

import pytest

from app.application.access_control import ActorContext, AuthorizationService
from app.application.corporate import CorporateAccessService
from app.application.corporate.change_corporate_status import (
    ChangeCorporateStatusCommand,
    ChangeCorporateStatusUseCase,
)
from app.application.corporate.get_corporate import GetCorporateUseCase
from app.base.application.exceptions import AuthorizationError
from app.domain.corporate import CorporateStatus
from tests.application.corporate.helpers import save_corporate
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


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
    use_case = ChangeCorporateStatusUseCase(repository, access)

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
    use_case = ChangeCorporateStatusUseCase(repository, access)

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
    use_case = ChangeCorporateStatusUseCase(repository, access)

    # Act & Assert
    with pytest.raises(AuthorizationError):
        await use_case.execute(
            ChangeCorporateStatusCommand(
                corporate_id=str(corporate.id.value),
                is_active=False,
            )
        )
