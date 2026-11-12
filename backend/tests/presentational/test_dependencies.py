"""FastAPIセキュリティ依存関係の検証テスト。"""

from __future__ import annotations

import pytest

from app.application.access_control.boundary_models import ActorContext, ActorRole
from app.application.common.exceptions import AuthorizationError
from app.domain.corporate.identifiers import CorporateId
from app.presentational.dependencies import require_admin_actor


@pytest.mark.anyio
async def test_require_admin_actor_管理者ロールを持つ場合は通過する() -> None:
    corporate_id = CorporateId.generate()
    admin_actor = ActorContext.corporate_admin(
        principal_id="admin-001", corporate_id=corporate_id
    )

    result = await require_admin_actor(admin_actor)
    assert result == admin_actor


@pytest.mark.anyio
async def test_require_admin_actor_運営者の場合も通過する() -> None:
    vendor_admin = ActorContext.vendor_system_admin(principal_id="vendor-001")

    result = await require_admin_actor(vendor_admin)
    assert result == vendor_admin


@pytest.mark.anyio
async def test_require_admin_actor_一般ロールの場合は認可エラーとなる() -> None:
    general_actor = ActorContext(
        principal_id="user-001",
        roles=frozenset({ActorRole.MEMBER}),
        corporate_id=CorporateId.generate(),
    )

    with pytest.raises(AuthorizationError) as exc_info:
        await require_admin_actor(general_actor)

    assert "管理者権限が必要です" in str(exc_info.value)
