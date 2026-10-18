"""契約登録から初回変更・権限解決までを実DBとHTTPで確認する。"""

import asyncio
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.bootstrap import create_app
from app.dev_main import StaticTokenActorContextProvider
from app.infrastructure.identity.local_authentication import PostgresLocalAuthentication
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
