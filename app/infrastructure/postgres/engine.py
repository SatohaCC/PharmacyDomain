"""SQLAlchemy 非同期エンジンとセッションファクトリ。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.postgres.settings import PostgresSettings


def create_async_engine_from_settings(settings: PostgresSettings) -> AsyncEngine:
    """設定に基づく非同期 PostgreSQL エンジンを生成する。"""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        connect_args={"command_timeout": settings.command_timeout},
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """コミット後も明示的に再取得できるセッションファクトリを生成する。"""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
