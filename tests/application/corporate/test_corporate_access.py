from __future__ import annotations

import pytest

from app.application.access_control import (
    ActorContext,
    AuthorizationService,
    CorporateAccessBoundary,
    Permission,
    TenantBoundaryNotFoundError,
)
from app.application.corporate import (
    CorporateAccessService,
    CorporateApplicationError,
    CorporateInactiveError,
    CorporateNotFoundError,
)
from app.base.application.exceptions import AuthorizationError, NotFoundError
from app.domain.corporate import CorporateId, CorporateStatus
from tests.application.corporate.helpers import save_corporate
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


def create_vendor_access(
    repository: InMemoryCorporateRepository,
    principal_id: str = "vendor-admin-1",
) -> CorporateAccessService:
    return CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.vendor_system_admin(principal_id=principal_id)
        ),
    )


def test_corporate_access_service_satisfies_boundary_protocol() -> None:
    """Store / Staff が依存する Protocol に実装が適合していることを固定する。

    ズレは mypy が型エラーとして検出し、この代入が実行時にも通ることで
    シグネチャの取り違えに気づける。
    """
    # Arrange
    repository = InMemoryCorporateRepository()

    # Act
    boundary: CorporateAccessBoundary = create_vendor_access(repository)

    # Assert
    assert boundary.require_active is not None


def test_corporate_not_found_uses_not_found_hierarchy() -> None:
    # Assert
    assert issubclass(CorporateNotFoundError, NotFoundError)
    assert not issubclass(CorporateNotFoundError, CorporateApplicationError)


@pytest.mark.asyncio
async def test_require_active_missing_corporate_raises_not_found() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    access = create_vendor_access(repository)

    # Act & Assert
    with pytest.raises(CorporateNotFoundError):
        await access.require_active(
            corporate_id=CorporateId.generate(),
            permission=Permission.VIEW_STORE,
        )


@pytest.mark.asyncio
async def test_require_active_inactive_corporate_raises_inactive() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    await repository.save(corporate.deactivate())
    access = create_vendor_access(repository)

    # Act & Assert
    with pytest.raises(CorporateInactiveError):
        await access.require_active(
            corporate_id=corporate.id,
            permission=Permission.MANAGE_STAFF,
        )


@pytest.mark.asyncio
async def test_require_existing_inactive_corporate_returns_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    corporate = await save_corporate(repository)
    inactive = corporate.deactivate()
    await repository.save(inactive)
    access = create_vendor_access(repository)

    # Act
    actual = await access.require_existing(
        corporate_id=corporate.id,
        permission=Permission.MANAGE_CORPORATE_STATUS,
    )

    # Assert
    assert actual.status is CorporateStatus.INACTIVE


@pytest.mark.asyncio
async def test_corporate_admin_own_corporate_returns_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    own_corp = await save_corporate(repository)
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=own_corp.id,
            )
        ),
    )

    # Act
    loaded = await access.require_active(
        corporate_id=own_corp.id,
        permission=Permission.MANAGE_STAFF,
    )

    # Assert
    assert loaded.id == own_corp.id


@pytest.mark.asyncio
async def test_corporate_admin_other_corporate_require_active_raises_boundary_not_found() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    own_corp = await save_corporate(repository)
    other_corp = await save_corporate(repository, name="別法人")
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=own_corp.id,
            )
        ),
    )

    # Act & Assert
    with pytest.raises(TenantBoundaryNotFoundError):
        await access.require_active(
            corporate_id=other_corp.id,
            permission=Permission.MANAGE_STAFF,
        )


@pytest.mark.asyncio
async def test_corporate_admin_other_corporate_require_existing_raises_boundary_not_found() -> (
    None
):
    # Arrange
    repository = InMemoryCorporateRepository()
    own_corp = await save_corporate(repository)
    other_corp = await save_corporate(repository, name="別法人")
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=own_corp.id,
            )
        ),
    )

    # Act & Assert
    with pytest.raises(TenantBoundaryNotFoundError):
        await access.require_existing(
            corporate_id=other_corp.id,
            permission=Permission.VIEW_CORPORATE,
        )


@pytest.mark.asyncio
async def test_corporate_admin_vendor_operation_raises_authorization_error() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    own_corp = await save_corporate(repository)
    access = CorporateAccessService(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="corp-admin-1",
                corporate_id=own_corp.id,
            )
        ),
    )

    # Act & Assert
    with pytest.raises(AuthorizationError):
        access.require_vendor_system_admin(permission=Permission.REGISTER_CORPORATE)
