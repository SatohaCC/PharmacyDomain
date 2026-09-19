"""開発・検証用シードを、実PostgreSQLと本番の組み立てで検証する。

シードが本当に要るのは「外部キーの向き」と「二度目の実行」である。どちらも
DBなしのテストでは確かめられない。``ON CONFLICT`` が何行に当たるか、複合外部
キーが組として参照できているかはサーバが決める。

投入したあと、その主体で**HTTP経由の更新が監査ごと確定すること**まで確かめる。
シードの目的は行を作ることではなく、開発用の起動点が実際に業務操作を通せる
状態を作ることだからである。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control import ActorRole
from app.application.identity.resolve_actor import VerifiedSubject
from app.domain.store.lifecycle import StoreStatus, StoreStatusReason
from app.infrastructure.di import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from app.presentational.app_factory import create_app
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from app.presentational.dev_main import build_actor_provider
from tests.fakes.fake_clock import FakeClock
from tests.tools.test_seed_dev_data import _environment
from tools.seed_dev_data import SeedData, apply_seed, build_seed_data

#: シードが行を作るテーブルと、1回適用したあとの行数。
SEEDED_TABLES: tuple[tuple[str, int], ...] = (
    ("account_people", 2),
    ("user_accounts", 2),
    ("corporates", 1),
    ("stores", 1),
    ("staff_members", 1),
    ("staff_person_links", 1),
    ("corporate_memberships", 1),
    ("store_manager_assignments", 1),
)

_DEV_TOKEN = "seed-integration-token"
_CLOCK = FakeClock(datetime(2026, 9, 20, 3, tzinfo=UTC))


async def _apply_seed_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> SeedData:
    """シードを1回適用して確定する。"""
    data = build_seed_data()
    async with PostgresUnitOfWork(session_factory) as work:
        await apply_seed(work, data)
        await work.commit()
    return data


async def _snapshot(engine: AsyncEngine) -> dict[str, list[tuple[uuid.UUID, int]]]:
    """シード対象テーブルの (id, version) を読み出す。"""
    snapshot: dict[str, list[tuple[uuid.UUID, int]]] = {}
    async with engine.connect() as connection:
        for table, _ in SEEDED_TABLES:
            rows = (
                await connection.execute(
                    text(f"SELECT id, version FROM {table} ORDER BY id")
                )
            ).all()
            snapshot[table] = [(row[0], row[1]) for row in rows]
    return snapshot


async def _count(engine: AsyncEngine, table: str) -> int:
    """1テーブルの行数を数える。"""
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one()
        )


def _seed_app(root: PostgresCompositionRoot, data: SeedData) -> FastAPI:
    """シードが出力した環境変数だけで、本番の組み立てを起動する。"""
    provider = build_actor_provider(
        {**_environment(data), "DEV_ACTOR_TOKEN": _DEV_TOKEN}
    )
    app = create_app(actor_provider=provider)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(actor_provider=provider, composition_root=root),
    )
    return app


@pytest.mark.asyncio
async def test_シードを適用すると_必要な行が揃う(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-20: 外部キーの向きが違えば、最初の適用がここで落ちる。"""
    # Act
    await _apply_seed_once(session_factory)

    # Assert
    for table, expected in SEEDED_TABLES:
        assert await _count(engine, table) == expected, f"{table} の行数が違う"


@pytest.mark.asyncio
async def test_シードを二度適用しても_行が増えず版も上がらない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-21: 読まずに保存すると ON CONFLICT DO NOTHING が0行になり落ちる。"""
    # Arrange
    await _apply_seed_once(session_factory)
    before = await _snapshot(engine)

    # Act
    await _apply_seed_once(session_factory)

    # Assert
    assert await _snapshot(engine) == before


@pytest.mark.asyncio
async def test_シードしたベンダー本人が_操作主体として解決できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-22: external_subject が未固定だと ResolveActorUseCase が拒否する。"""
    # Arrange
    data = await _apply_seed_once(session_factory)
    root = PostgresCompositionRoot(engine, session_factory, _CLOCK)
    subject = data.vendor_account.external_subject
    assert subject is not None

    # Act
    actor = await root.resolve_identity(VerifiedSubject(principal_id=subject.value))

    # Assert
    assert actor.roles == frozenset({ActorRole.VENDOR_SYSTEM_ADMIN})
    assert actor.account_id == data.vendor_account.id


@pytest.mark.asyncio
async def test_シードした法人管理者が_自法人の主体として解決できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-23: 法人アクセス権とスタッフ対応が揃っていないと解決できない。"""
    # Arrange
    data = await _apply_seed_once(session_factory)
    root = PostgresCompositionRoot(engine, session_factory, _CLOCK)
    subject = data.admin_account.external_subject
    assert subject is not None

    # Act
    actor = await root.resolve_identity(VerifiedSubject(principal_id=subject.value))

    # Assert
    assert actor.roles == frozenset({ActorRole.CORPORATE_ADMIN})
    assert actor.corporate_id == data.corporate.id
    assert actor.staff_id == data.staff.id


@pytest.mark.asyncio
async def test_シードは_監査行を作らない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-24: シードは業務操作ではない。確定の経路を2つにしない。"""
    # Act
    await _apply_seed_once(session_factory)

    # Assert
    assert await _count(engine, "operation_audits") == 0


@pytest.mark.asyncio
async def test_シードした主体なら_HTTP経由の更新が監査ごと確定する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-25: 要件の核心。監査行は user_accounts への複合外部キーを持つ。"""
    # Arrange
    data = await _apply_seed_once(session_factory)
    root = PostgresCompositionRoot(engine, session_factory, _CLOCK)

    # Act
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_seed_app(root, data)),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_DEV_TOKEN}"},
    ) as client:
        response = await client.patch(
            f"/corporates/{data.corporate.id.value}/name",
            json={"name": "シード確認薬局グループ"},
        )

    # Assert
    assert response.status_code == 204, response.text
    async with engine.connect() as connection:
        audits = (
            await connection.execute(
                text("SELECT person_id, account_id FROM operation_audits")
            )
        ).all()
    assert len(audits) == 1
    assert audits[0][0] == data.vendor_person.id.value
    assert audits[0][1] == data.vendor_account.id.value


@pytest.mark.asyncio
async def test_シードした店舗は_管理薬剤師が在任している(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-26: 在任が無いと、受付も調剤も薬歴の作成も始められない。"""
    # Arrange
    data = await _apply_seed_once(session_factory)

    # Act
    async with PostgresUnitOfWork(session_factory) as work:
        effective = await PostgresRepositorySet.create(
            work
        ).manager_assignment.find_effective(
            data.corporate.id,
            data.store.id,
            data.manager_assignment.period.starts_on,
        )

    # Assert
    assert effective is not None
    assert effective.id == data.manager_assignment.id


@pytest.mark.asyncio
async def test_シードは_既存行を上書きしない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-27: 手で変えた開発用データをシードが黙って戻すと驚きが大きい。"""
    # Arrange
    data = await _apply_seed_once(session_factory)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        store = await repositories.store.get(data.store.id)
        assert store is not None
        await repositories.store.save(
            store.change_status(
                StoreStatus.SUSPENDED,
                reason=StoreStatusReason("シードの上書き確認"),
                person_id=data.vendor_person.id,
                account_id=data.vendor_account.id,
                recorded_at=_CLOCK.now(),
            )
        )
        await work.commit()

    # Act
    await _apply_seed_once(session_factory)

    # Assert
    async with PostgresUnitOfWork(session_factory) as work:
        stored = await PostgresRepositorySet.create(work).store.get(data.store.id)
    assert stored is not None
    assert stored.status == StoreStatus.SUSPENDED
