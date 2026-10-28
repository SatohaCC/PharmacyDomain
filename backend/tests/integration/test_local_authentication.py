"""契約登録から初回変更・権限解決までを実DBとHTTPで確認する。"""

import asyncio
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.boundary_models import ResolvedActorContext
from app.application.identity.commands.models import AccountStatus
from app.bootstrap import create_app
from app.dev_main import StaticTokenActorContextProvider
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
    PostgresLocalAuthentication,
)
from app.infrastructure.identity.postgres.user_account import (
    PostgresUserAccountRepository,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import (
    corporates,
    local_credentials,
    local_sessions,
)
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.fakes.fake_clock import FakeClock
from tests.integration.organization_helpers import Organization, setup_organization

INITIAL = "test-initial-password-12345"
CHANGED = "test-personal-password-67890"


@pytest.mark.asyncio
async def test_ローカル認証_法人所属のない有効なベンダーは利用開始できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    actor = fixture.authorization.actor
    assert isinstance(actor, ResolvedActorContext)
    async with PostgresUnitOfWork(session_factory) as work:
        account = await PostgresUserAccountRepository(work).get(actor.account_id)
        assert account is not None and account.external_subject is not None
        await PostgresCredentialWriter(work).issue(
            "test-vendor", INITIAL, account.external_subject.value
        )
        await work.commit()
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        login = await client.post(
            "/auth/login", json={"login_id": "test-vendor", "password": INITIAL}
        )
        assert login.status_code == 200, login.text
        changed = await client.post(
            "/auth/password",
            json={"password": CHANGED},
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        # Assert
        assert changed.status_code == 200, changed.text
        me = await client.get(
            "/me", headers={"Authorization": f"Bearer {changed.json()['access_token']}"}
        )
        assert me.status_code == 200, me.text
        assert me.json()["roles"] == ["vendor_system_admin"]


@pytest.mark.asyncio
@pytest.mark.parametrize("suspension", ["account", "membership"])
@pytest.mark.parametrize("changed", [False, True])
async def test_ローカル認証_停止後は正しいパスワードでもログインと初回変更を拒否する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    suspension: str,
    changed: bool,
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    subject = fixture.accounts[0].external_subject
    assert subject is not None
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresCredentialWriter(work).issue("test-admin", INITIAL, subject.value)
        await work.commit()
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        login = await client.post(
            "/auth/login", json={"login_id": "test-admin", "password": INITIAL}
        )
        assert login.status_code == 200, login.text
        initial_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        if changed:
            response = await client.post(
                "/auth/password", json={"password": CHANGED}, headers=initial_headers
            )
            assert response.status_code == 200, response.text
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            if suspension == "account":
                await scope.use_cases.identity.suspend_account.execute(
                    str(fixture.accounts[0].id.value)
                )
            else:
                await scope.use_cases.identity.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[0].id.value),
                    status=AccountStatus.SUSPENDED,
                )
        async with session_factory() as session:
            previous_hash = await session.scalar(
                select(local_credentials.c.password_hash)
            )
            previous_sessions = await session.scalar(
                select(func.count()).select_from(local_sessions)
            )
        # Act
        correct = await client.post(
            "/auth/login",
            json={
                "login_id": "test-admin",
                "password": CHANGED if changed else INITIAL,
            },
        )
        incorrect = await client.post(
            "/auth/login", json={"login_id": "test-admin", "password": "wrong"}
        )
        reset = await client.post(
            "/auth/password",
            json={"password": "test-another-password-13579"},
            headers=initial_headers,
        )
        # Assert
        assert correct.status_code == incorrect.status_code == reset.status_code == 401
        assert correct.json() == incorrect.json() == reset.json()
        async with session_factory() as session:
            assert (
                await session.scalar(select(local_credentials.c.password_hash))
                == previous_hash
            )
            assert (
                await session.scalar(select(func.count()).select_from(local_sessions))
                == previous_sessions
            )


def contract_body(
    login_id: str = "test-admin", name: str = "テスト新規契約法人"
) -> dict[str, object]:
    """メールや招待入力を持たない契約データ。"""
    return {
        "name": name,
        "representative_last_name": "テスト",
        "representative_first_name": "代表",
        "administrator": {
            "last_name": "テスト",
            "first_name": "管理者",
            "last_name_kana": "テスト",
            "first_name_kana": "カンリシャ",
        },
        "login_id": login_id,
        "initial_password": INITIAL,
    }


def local_app(fixture: Organization) -> httpx.ASGITransport:
    """ベンダー操作だけを固定し、利用者の認証は実装を使う。"""
    app = create_app()
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=StaticTokenActorContextProvider(
                token="vendor", actor=fixture.authorization.actor
            ),
            composition_root=fixture.root,
            local_authentication=PostgresLocalAuthentication(
                fixture.root.session_factory, fixture.root.clock
            ),
        ),
    )
    return httpx.ASGITransport(app=app)


@pytest.mark.asyncio
async def test_新規契約_招待なしで登録し初回変更後にだけ業務を利用できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        assert (
            await client.post("/contracts", json=contract_body())
        ).status_code == 401
        created = await client.post(
            "/contracts",
            json=contract_body(),
            headers={"Authorization": "Bearer vendor"},
        )
        assert created.status_code == 201, created.text
        corporate_id = created.json()["id"]
        login = await client.post(
            "/auth/login", json={"login_id": "TEST-ADMIN", "password": INITIAL}
        )
        assert login.status_code == 200, login.text
        assert login.headers["cache-control"] == "no-store"
        assert login.json()["password_change_required"] is True
        initial_token = login.json()["access_token"]
        initial_headers = {"Authorization": f"Bearer {initial_token}"}
        # Assert
        assert (await client.get("/me", headers=initial_headers)).status_code == 401
        same = await client.post(
            "/auth/password", json={"password": INITIAL}, headers=initial_headers
        )
        assert same.status_code == 422, same.text
        changed = await client.post(
            "/auth/password", json={"password": CHANGED}, headers=initial_headers
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["password_change_required"] is False
        headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
        me = await client.get("/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["corporate_id"] == corporate_id
        assert me.json()["roles"] == ["corporate_admin"]
        assert (
            await client.post(
                "/auth/password", json={"password": INITIAL}, headers=headers
            )
        ).status_code == 401
        forbidden = await client.post(
            "/contracts",
            json=contract_body("test-other", "テスト別法人"),
            headers=headers,
        )
        assert forbidden.status_code == 403
        hidden = await client.get(
            f"/corporates/{fixture.corporate.id.value}", headers=headers
        )
        assert hidden.status_code == 404
        assert (await client.get("/me", headers=initial_headers)).status_code == 401
        assert (
            await client.post(
                "/auth/password", json={"password": INITIAL}, headers=initial_headers
            )
        ).status_code == 401
        assert (
            await client.post(
                "/auth/login", json={"login_id": "test-admin", "password": INITIAL}
            )
        ).status_code == 401
        assert (await client.post("/auth/logout", headers=headers)).status_code == 204
        assert (await client.get("/me", headers=headers)).status_code == 401
        again = await client.post(
            "/auth/login", json={"login_id": "test-admin", "password": CHANGED}
        )
        assert again.status_code == 200
        async with session_factory() as session:
            stored = (await session.execute(select(local_credentials))).mappings().one()
            assert INITIAL not in str(stored) and CHANGED not in str(stored)
            assert again.json()["access_token"] not in str(
                (await session.execute(select(local_sessions))).all()
            )


@pytest.mark.asyncio
async def test_新規契約_ログインID重複と不正入力では法人も残さない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    async with httpx.AsyncClient(
        transport=local_app(fixture),
        base_url="http://test",
        headers={"Authorization": "Bearer vendor"},
    ) as client:
        assert (
            await client.post("/contracts", json=contract_body())
        ).status_code == 201
        # Act / Assert
        for login_id, status in [("test-admin", 409), ("不正なID", 422)]:
            denied = await client.post(
                "/contracts", json=contract_body(login_id, "テスト失敗法人")
            )
            assert denied.status_code == status, denied.text
        async with session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(corporates))
            ) == 2
            assert (
                await session.scalar(
                    select(func.count()).select_from(local_credentials)
                )
            ) == 1


@pytest.mark.asyncio
async def test_ローカル認証_連続失敗と期限切れを拒否する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    assert isinstance(fixture.root.clock, FakeClock)
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        assert (
            await client.post(
                "/contracts",
                json=contract_body(),
                headers={"Authorization": "Bearer vendor"},
            )
        ).status_code == 201
        # Act / Assert
        for _ in range(5):
            assert (
                await client.post(
                    "/auth/login", json={"login_id": "test-admin", "password": "wrong"}
                )
            ).status_code == 401
        assert (
            await client.post(
                "/auth/login", json={"login_id": "test-admin", "password": INITIAL}
            )
        ).status_code == 401
        fixture.root.clock.advance(timedelta(minutes=16))
        login = await client.post(
            "/auth/login", json={"login_id": "test-admin", "password": INITIAL}
        )
        assert login.status_code == 200, login.text
        fixture.root.clock.advance(timedelta(minutes=11))
        expired = await client.post(
            "/auth/password",
            json={"password": CHANGED},
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert expired.status_code == 401


@pytest.mark.asyncio
async def test_初回変更_同じセッションの同時使用は一度だけ成功する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        await client.post(
            "/contracts",
            json=contract_body(),
            headers={"Authorization": "Bearer vendor"},
        )
        login = await client.post(
            "/auth/login", json={"login_id": "test-admin", "password": INITIAL}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        # Act
        responses = await asyncio.gather(
            *[
                client.post(
                    "/auth/password", json={"password": password}, headers=headers
                )
                for password in [CHANGED, "test-another-password-13579"]
            ]
        )
        # Assert
        assert sorted(response.status_code for response in responses) == [200, 401]
