"""法人権限と、期間付きの店舗管理権限の加算を検証する。"""

from dataclasses import replace
from datetime import date

import pytest

from app.application.access_control.boundary_models import ActorRole, UserPermissionType
from app.application.identity.commands.dtos.identity_views import CurrentActorDto
from app.application.identity.errors import UnavailableIdentityError
from app.application.identity.queries.dtos.identity_resolution import (
    ManagerIdentitySnapshot,
)
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.identity.primitives import MembershipRole
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import ManagerAssignmentStatus
from tests.application.identity.test_actor_resolution_boundary import (
    _SUBJECT,
    SnapshotIdentityReader,
    _snapshot,
)
from tests.fakes.fake_clock import FakeClock


@pytest.mark.asyncio
async def test_法人管理者_店舗にも所属すると_法人権限と一般業務権限を両方持つ() -> None:
    # Arrange
    facts = _snapshot()
    assert facts.membership is not None
    facts = replace(
        facts, membership=replace(facts.membership, role=MembershipRole.CORPORATE_ADMIN)
    )
    # Act
    actor = await ResolveActorUseCase(
        SnapshotIdentityReader(facts), FakeClock()
    ).execute(_SUBJECT)
    # Assert
    assert actor.roles == frozenset(
        {ActorRole.CORPORATE_ADMIN, ActorRole.STORE_OPERATOR}
    )
    public = CurrentActorDto.from_actor(actor)
    assert {(item.permission_type, item.store_id) for item in public.permissions} == {
        (UserPermissionType.CORPORATE_ADMIN, None),
        (UserPermissionType.GENERAL_USER, str(next(iter(actor.store_ids)).value)),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,starts_on,ends_on,expected",
    [
        (ManagerAssignmentStatus.CONFIRMED, date(2026, 8, 23), date(2026, 8, 23), True),
        (ManagerAssignmentStatus.CONFIRMED, date(2026, 8, 24), None, False),
        (ManagerAssignmentStatus.CONFIRMED, date(2026, 8, 1), date(2026, 8, 22), False),
        (ManagerAssignmentStatus.CANCELLED, date(2026, 8, 1), None, False),
    ],
)
async def test_管理薬剤師_有効な任命期間だけ_店舗管理権限を持つ(
    status: ManagerAssignmentStatus,
    starts_on: date,
    ends_on: date | None,
    expected: bool,
) -> None:
    # Arrange
    facts = _snapshot()
    membership = facts.membership
    assert (
        membership is not None
        and membership.staff_id is not None
        and facts.person_id is not None
    )
    store = next(iter(membership.store_ids))
    assignment = ManagerIdentitySnapshot(
        corporate_id=membership.corporate_id,
        store_id=store,
        staff_id=membership.staff_id,
        person_id=facts.person_id,
        status=status,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    facts = replace(
        facts, membership=replace(membership, manager_assignments=(assignment,))
    )
    # Act
    actor = await ResolveActorUseCase(
        SnapshotIdentityReader(facts), FakeClock()
    ).execute(_SUBJECT)
    # Assert
    assert (ActorRole.STORE_MANAGER in actor.roles) is expected
    assert actor.managed_store_ids == (frozenset({store}) if expected else frozenset())
    # 他店舗への権限付与が保存済みでも認証境界で拒否する。
    if expected:
        assert facts.membership is not None
        invalid = replace(
            facts,
            membership=replace(
                facts.membership, store_ids=membership.store_ids | {StoreId.generate()}
            ),
        )
        with pytest.raises(UnavailableIdentityError):
            await ResolveActorUseCase(
                SnapshotIdentityReader(invalid), FakeClock()
            ).execute(_SUBJECT)
