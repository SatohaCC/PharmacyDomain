"""操作者の有効性判断を、永続化実装と独立してApplicationで検証する。"""

from dataclasses import replace

import pytest

from app.application.access_control.boundary_models import ActorRole
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.errors import UnavailableIdentityError
from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
    MembershipIdentitySnapshot,
)
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId

_SUBJECT = VerifiedSubject(principal_id="issuer/テスト操作者")


class SnapshotIdentityReader(ResolveActorQueryReader):
    """取得結果を渡すだけで、利用状態やロールを判定しない読取フェイク。"""

    def __init__(self, result: IdentityResolutionSnapshot | None) -> None:
        self.result = result
        self.subject: ExternalSubjectKey | None = None

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> IdentityResolutionSnapshot | None:
        self.subject = subject
        return self.result


def _snapshot() -> IdentityResolutionSnapshot:
    person_id = AccountPersonId.generate()
    account_id = UserAccountId.generate()
    return IdentityResolutionSnapshot(
        account_id=account_id,
        account_person_id=person_id,
        person_id=person_id,
        external_subject=ExternalSubjectKey(_SUBJECT.principal_id),
        account_status=AccountStatus.ACTIVE,
        is_vendor_admin=False,
        membership=MembershipIdentitySnapshot(
            id=CorporateMembershipId.generate(),
            account_id=account_id,
            corporate_id=CorporateId.generate(),
            status=AccountStatus.ACTIVE,
            role=MembershipRole.STORE_VIEWER,
            staff_id=StaffId.generate(),
            store_ids=frozenset({StoreId.generate()}),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("vendor", [False, True])
async def test_操作者解決_Readerが停止アカウントを返しても_Applicationが拒否する(
    vendor: bool,
) -> None:
    # Arrange
    facts = replace(
        _snapshot(), account_status=AccountStatus.SUSPENDED, is_vendor_admin=vendor
    )
    reader = SnapshotIdentityReader(facts)
    use_case = ResolveActorUseCase(reader)
    # Act / Assert
    with pytest.raises(UnavailableIdentityError):
        await use_case.execute(_SUBJECT)
    assert reader.subject == ExternalSubjectKey(_SUBJECT.principal_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing",
    [
        "account",
        "person",
        "membership",
        "subject",
        "foreign_person",
        "foreign_membership",
        "stopped_membership",
    ],
)
async def test_操作者解決_参照事実が欠落または不一致なら_Applicationが拒否する(
    missing: str,
) -> None:
    # Arrange
    original = _snapshot()
    membership = original.membership
    assert membership is not None
    facts: IdentityResolutionSnapshot | None = original
    if missing == "account":
        facts = None
    elif missing == "person":
        facts = replace(original, person_id=None)
    elif missing == "membership":
        facts = replace(original, membership=None)
    elif missing == "subject":
        facts = replace(
            original, external_subject=ExternalSubjectKey("issuer/別の主体")
        )
    elif missing == "foreign_person":
        facts = replace(original, person_id=AccountPersonId.generate())
    elif missing == "foreign_membership":
        facts = replace(
            original,
            membership=replace(membership, account_id=UserAccountId.generate()),
        )
    else:
        facts = replace(
            original, membership=replace(membership, status=AccountStatus.SUSPENDED)
        )
    use_case = ResolveActorUseCase(SnapshotIdentityReader(facts))
    # Act / Assert
    with pytest.raises(UnavailableIdentityError):
        await use_case.execute(_SUBJECT)


@pytest.mark.asyncio
async def test_操作者解決_有効な所属の事実から_Applicationがロールと店舗範囲を構築する() -> (
    None
):
    # Arrange
    facts = _snapshot()
    assert facts.membership is not None
    use_case = ResolveActorUseCase(SnapshotIdentityReader(facts))
    # Act
    actor = await use_case.execute(_SUBJECT)
    # Assert
    assert actor.roles == frozenset({ActorRole.STORE_VIEWER})
    assert actor.account_id == facts.account_id
    assert actor.person_id == facts.person_id
    assert actor.membership_id == facts.membership.id
    assert actor.corporate_id == facts.membership.corporate_id
    assert actor.store_ids == facts.membership.store_ids


@pytest.mark.asyncio
async def test_操作者解決_有効なベンダー管理者なら_所属停止と分離して権限を構築する() -> (
    None
):
    # Arrange
    facts = _snapshot()
    assert facts.membership is not None
    facts = replace(
        facts,
        is_vendor_admin=True,
        membership=replace(facts.membership, status=AccountStatus.SUSPENDED),
    )
    use_case = ResolveActorUseCase(SnapshotIdentityReader(facts))
    # Act
    actor = await use_case.execute(_SUBJECT)
    # Assert
    assert actor.roles == frozenset({ActorRole.VENDOR_SYSTEM_ADMIN})
    assert actor.corporate_id is None
    assert actor.membership_id is None
    assert actor.store_ids == frozenset()
