"""本人確認から最新の権限・SQL範囲までをHTTP経由で検証する。"""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.identity.resolve_actor import VerifiedIdentity
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.presentational.app_factory import create_app
from app.presentational.authentication import UnconfiguredActorContextProvider
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.fakes.verified_identity_provider import StubVerifiedIdentityProvider
from tests.integration.organization_helpers import (
    Organization,
    external_subject_of,
    setup_organization,
)


def identity_app(fixture: Organization) -> FastAPI:
    """本番配線を使い、本人確認基盤の結果だけを固定する。"""
    provider = StubVerifiedIdentityProvider(
        {
            "person": VerifiedIdentity(
                person_id=fixture.accounts[0].person_id,
                principal_id=external_subject_of(0),
            )
        }
    )
    app = create_app(identity_provider=provider)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=UnconfiguredActorContextProvider(),
            composition_root=fixture.root,
            identity_provider=provider,
        ),
    )
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["membership", "account", "scope", "role"])
async def test_同じ資格情報でも権限変更は次のHTTP要求へ反映される(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], change: str
) -> None:
    fixture = await setup_organization(engine, session_factory)
    app = identity_app(fixture)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer person"},
    ) as client:
        before = await client.get("/me")
        assert before.status_code == 200, before.text
        assert before.json()["person_id"] == str(fixture.accounts[0].person_id.value)
        assert before.json()["account_id"] == str(fixture.accounts[0].id.value)
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            service = scope.use_cases.identity
            if change == "account":
                await service.suspend_account.execute(str(fixture.accounts[0].id.value))
            elif change == "membership":
                await service.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[0].id.value),
                    status=AccountStatus.SUSPENDED,
                )
            else:
                await service.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[0].id.value),
                    role=MembershipRole.STORE_VIEWER,
                    store_ids=()
                    if change == "scope"
                    else (str(fixture.store.id.value),),
                )
        after = await client.get("/me")
        if change in {"account", "membership"}:
            assert after.status_code == 401, after.text
        else:
            assert after.status_code == 200, after.text
            assert after.json()["roles"] == ["store_viewer"]
            stores = await client.get(
                f"/corporates/{fixture.corporate.id.value}/stores"
            )
            assert stores.status_code == 200, stores.text
            assert len(stores.json()) == (0 if change == "scope" else 1)
            detail = await client.get(
                f"/corporates/{fixture.corporate.id.value}/stores/{fixture.store.id.value}"
            )
            assert detail.status_code == (404 if change == "scope" else 200), (
                detail.text
            )
            denied = await client.post(
                f"/corporates/{fixture.corporate.id.value}/stores/{fixture.store.id.value}/suspension",
                json={"reason": "権限のない変更"},
            )
            assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [MembershipRole.STORE_OPERATOR, MembershipRole.STORE_VIEWER]
)
async def test_店舗ロールはスタッフ最小情報だけ取得でき法人台帳と昇格は拒否される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    role: MembershipRole,
) -> None:
    fixture = await setup_organization(engine, session_factory)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.identity.change_membership.execute(
            str(fixture.corporate.id.value),
            str(fixture.memberships[0].id.value),
            role=role,
            store_ids=(str(fixture.store.id.value),),
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=identity_app(fixture)),
        base_url="http://test",
        headers={"Authorization": "Bearer person"},
    ) as client:
        staff = await client.get(
            f"/corporates/{fixture.corporate.id.value}/staffs/{fixture.staff[0].id.value}"
        )
        assert staff.status_code == 200, staff.text
        assert "email" not in staff.json() and "phone_number" not in staff.json()
        patients = await client.get(
            f"/corporates/{fixture.corporate.id.value}/patients/{fixture.staff[0].id.value}"
        )
        assert patients.status_code == 403, patients.text
        users = await client.get(f"/corporates/{fixture.corporate.id.value}/users")
        assert users.status_code == 403, users.text
        escalation = await client.patch(
            f"/corporates/{fixture.corporate.id.value}/users/{fixture.memberships[0].id.value}",
            json={"role": "corporate_admin"},
        )
        assert escalation.status_code == 403, escalation.text
