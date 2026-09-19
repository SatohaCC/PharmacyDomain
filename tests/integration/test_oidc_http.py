"""外部IdPのトークンから、実DBの本人・権限までをHTTP経由で通す。

本番の ``create_app()`` に**本物のJWT検証実装**を差し込む。スタブで置き換えるのは
署名鍵の取得だけで、検証・主体の組み立て・本人の解決・認可・SQLの取得範囲は
production の経路をそのまま通る。
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.identity.invite_user import InviteUserCommand
from app.domain.identity.primitives import (
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.user_account import UserAccount
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from app.presentational.app_factory import create_app
from app.presentational.authentication import UnconfiguredActorContextProvider
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from app.presentational.oidc import OidcSettings, OidcVerifiedSubjectProvider
from tests.factories.oidc_factory import issue_token, signing_key
from tests.fakes.signing_key_resolver import StubSigningKeyResolver
from tests.integration.organization_helpers import (
    Organization,
    external_subject_of,
    setup_organization,
)
from tests.integration.test_identity_persistence import _person

#: ``external_subject_of()`` が作る ``issuer/person-N`` と噛み合わせる。
#: 主体は「発行元 + sub」なので、この2つが揃って初めて実DBの行に当たる。
_ISSUER = "issuer"
_AUDIENCE = "pharmacydomain"
_SETTINGS = OidcSettings(
    issuer=_ISSUER,
    audience=_AUDIENCE,
    jwks_url="https://idp.example.test/.well-known/jwks.json",
)


def _token(subject: str, **overrides: object) -> str:
    """この組織に噛み合う発行元・利用者でトークンを発行する。"""
    return issue_token(
        issuer=_ISSUER,
        audience=_AUDIENCE,
        subject=subject,
        **overrides,  # type: ignore[arg-type]
    )


def _oidc_app(fixture: Organization) -> FastAPI:
    """本番配線に、本物のJWT検証実装を差し込む。"""
    provider = OidcVerifiedSubjectProvider(
        _SETTINGS, StubSigningKeyResolver(signing_key())
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


def _client(fixture: Organization, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_oidc_app(fixture)),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_署名したトークンで本人と権限が解決し業務ルートも通る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)

    # Act
    async with _client(fixture, _token("person-0")) as client:
        me = await client.get("/me")
        stores = await client.get(f"/corporates/{fixture.corporate.id.value}/stores")

    # Assert
    assert me.status_code == 200, me.text
    assert me.json()["person_id"] == str(fixture.accounts[0].person_id.value)
    assert me.json()["account_id"] == str(fixture.accounts[0].id.value)
    # 認証だけでなく、認可とSQLの取得範囲まで通っていることを確かめる。
    assert stores.status_code == 200, stores.text
    assert [item["id"] for item in stores.json()] == [str(fixture.store.id.value)]


@pytest.mark.asyncio
async def test_対応するアカウントの無い主体は401になる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """トークンの検証は通っても、内部にアカウントが無ければ主体は決まらない。"""
    # Arrange
    fixture = await setup_organization(engine, session_factory)

    # Act
    async with _client(fixture, _token("身に覚えのない主体")) as client:
        response = await client.get("/me")

    # Assert
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("flaw", ["期限切れ", "別の鍵で署名"])
async def test_検証できないトークンはHTTPで401になる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], flaw: str
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    overrides: dict[str, object] = (
        {"lifetime": timedelta(minutes=-5)}
        if flaw == "期限切れ"
        else {"signed_with": signing_key("別の鍵").private_pem}
    )

    # Act
    async with _client(fixture, _token("person-0", **overrides)) as client:
        response = await client.get(f"/corporates/{fixture.corporate.id.value}/stores")

    # Assert
    assert response.status_code == 401, response.text
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_アカウントを停止すると同じトークンでも次の要求は拒否される(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """トークン自体は期限まで有効だが、権限は毎要求読み直す。

    失効の仕組みを持たない代わりに、アカウントの状態をリクエストごとに確認する
    ことで、停止がその場で効くようにしている。
    """
    # Arrange
    fixture = await setup_organization(engine, session_factory)

    # Act
    async with _client(fixture, _token("person-0")) as client:
        before = await client.get("/me")
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.identity.suspend_account.execute(
                str(fixture.accounts[0].id.value)
            )
        after = await client.get("/me")

    # Assert
    assert before.status_code == 200, before.text
    assert after.status_code == 401, after.text


@pytest.mark.asyncio
async def test_検証済みの外部主体で招待を受諾するとアカウントが生まれる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """本人は招待から、外部主体は提示されたトークンから取る。"""
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    invited = _person()
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.repositories.account_person.save(invited)
        issued = await scope.use_cases.identity.invite.execute(
            InviteUserCommand(
                corporate_id=str(fixture.corporate.id.value),
                person_id=str(invited.id.value),
                addressee="invited@example.test",
                role=MembershipRole.CORPORATE_ADMIN,
                expires_at=fixture.root.clock.now() + timedelta(days=1),
            )
        )

    # Act
    async with _client(fixture, _token("新しい主体")) as client:
        accepted = await client.post(
            "/user-invitations/acceptance", json={"secret": issued.secret}
        )
        me = await client.get("/me")

    # Assert
    assert accepted.status_code == 200, accepted.text
    assert me.status_code == 200, me.text
    assert me.json()["person_id"] == str(invited.id.value)
    async with PostgresUnitOfWork(session_factory) as work:
        saved = await PostgresRepositorySet.create(work).user_account.get_by_person(
            invited.id
        )
    assert saved is not None
    assert saved.external_subject == ExternalSubjectKey(f"{_ISSUER}/新しい主体")


@pytest.mark.asyncio
async def test_他人に固定済みの外部主体ではHTTPでも受諾できない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """招待の秘密を握っても、他人の主体で新しいアカウントは作れない。"""
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    invited = _person()
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.repositories.account_person.save(invited)
        issued = await scope.use_cases.identity.invite.execute(
            InviteUserCommand(
                corporate_id=str(fixture.corporate.id.value),
                person_id=str(invited.id.value),
                addressee="invited@example.test",
                role=MembershipRole.CORPORATE_ADMIN,
                expires_at=fixture.root.clock.now() + timedelta(days=1),
            )
        )

    # Act: person-0 の主体は既に別の本人のアカウントへ固定されている。
    async with _client(fixture, _token("person-0")) as client:
        response = await client.post(
            "/user-invitations/acceptance", json={"secret": issued.secret}
        )

    # Assert
    assert response.status_code == 409, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        saved = await PostgresRepositorySet.create(work).user_account.get_by_person(
            invited.id
        )
    assert saved is None


@pytest.mark.asyncio
async def test_外部主体を固定していないアカウントは実DBでも主体では引けない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """``WHERE external_subject = :v`` は NULL の行に当たらない。

    未固定のアカウントがどの主体からも到達できないことは、分岐ではなく検索条件
    そのものが保証する。インメモリのFakeだけで確かめると、この保証がドライバの
    挙動に依存している事実が隠れる。
    """
    # Arrange
    del engine
    person = _person()
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.account_person.save(person)
        await repositories.user_account.save(
            UserAccount(id=UserAccountId.generate(), person_id=person.id)
        )
        await work.commit()

    # Act
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        by_subject = await repositories.user_account.get_by_subject(
            ExternalSubjectKey(external_subject_of(9))
        )
        by_person = await repositories.user_account.get_by_person(person.id)

    # Assert
    assert by_subject is None
    assert by_person is not None
    assert by_person.external_subject is None
