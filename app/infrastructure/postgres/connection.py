"""接続設定、非同期エンジン、セッションファクトリ、Unit of Work。

上から順に寿命が短くなる。設定とエンジンはプロセス、セッションファクトリはその
エンジンに紐づき、``PostgresUnitOfWork`` は1リクエスト（1トランザクション）で
使い捨てる。``AsyncSession`` は並行実行安全ではないので、この順序を崩して
セッションを使い回すと同時実行で壊れる。
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# --------------------------------------------------------------------------
# 接続設定
# --------------------------------------------------------------------------


class PostgresConfigurationError(ValueError):
    """PostgreSQL 接続設定が不足または不正な場合の例外。"""


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    """非同期 PostgreSQL エンジンへ渡す設定。"""

    database_url: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    command_timeout: float = 10.0

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> PostgresSettings:
        """環境変数から設定を読み込む。"""
        values = os.environ if environment is None else environment
        raw_url = values.get("DATABASE_URL", "").strip()
        if not raw_url:
            raise PostgresConfigurationError("DATABASE_URL が設定されていません。")
        database_url = _normalize_database_url(raw_url)
        return cls(
            database_url=database_url,
            pool_size=_positive_int(values, "POSTGRES_POOL_SIZE", default=5),
            max_overflow=_non_negative_int(values, "POSTGRES_MAX_OVERFLOW", default=10),
            pool_timeout=_positive_float(values, "POSTGRES_POOL_TIMEOUT", default=30.0),
            command_timeout=_positive_float(
                values, "POSTGRES_COMMAND_TIMEOUT", default=10.0
            ),
        )


def _normalize_database_url(raw_url: str) -> str:
    """同期用の URL を asyncpg 用へ正規化する。"""
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise PostgresConfigurationError(
        "DATABASE_URL は PostgreSQL の URL（postgresql:// または "
        "postgresql+asyncpg://）で指定してください。"
    )


def _positive_int(values: Mapping[str, str], key: str, *, default: int) -> int:
    value = _parse_int(values, key, default=default)
    if value <= 0:
        raise PostgresConfigurationError(f"{key} は1以上で指定してください。")
    return value


def _non_negative_int(values: Mapping[str, str], key: str, *, default: int) -> int:
    value = _parse_int(values, key, default=default)
    if value < 0:
        raise PostgresConfigurationError(f"{key} は0以上で指定してください。")
    return value


def _parse_int(values: Mapping[str, str], key: str, *, default: int) -> int:
    raw = values.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise PostgresConfigurationError(f"{key} は整数で指定してください。") from error


def _positive_float(values: Mapping[str, str], key: str, *, default: float) -> float:
    raw = values.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise PostgresConfigurationError(f"{key} は数値で指定してください。") from error
    if value <= 0:
        raise PostgresConfigurationError(f"{key} は0より大きく指定してください。")
    return value


# --------------------------------------------------------------------------
# エンジンとセッションファクトリ
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# Unit of Work
# --------------------------------------------------------------------------


class PostgresUnitOfWork:
    """一つの非同期セッションを複数のアダプタで共有する。

    ``AsyncSession`` は並行実行安全ではないため、このインスタンスは1リクエスト
    （1トランザクション）専用として組み立て、使い回さない。同じインスタンスを
    同時に開始しようとした場合は ``__aenter__`` が失敗する。

    読み込んだ行の世代（``version`` 列）もここで保持する。同じ集約を読み書き
    するのは同じトランザクションの中だけなので、追跡の寿命はトランザクションと
    一致する。Repository ごとに持たせると、複数のRepositoryが同じ行を読んだ
    ときに世代が分裂する。

    世代は集約 ID だけでなくテーブル名との組で追跡する。同じ UUID v7 が
    複数の集約で使われても、別集約の読み込みが楽観ロック情報を上書き
    しないようにするためである。
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._loaded_versions: dict[tuple[str, uuid.UUID], int] = {}

    @staticmethod
    def _version_key(namespace: str, aggregate_id: uuid.UUID) -> tuple[str, uuid.UUID]:
        return namespace, aggregate_id

    @property
    def session(self) -> AsyncSession:
        """現在のトランザクションで共有するセッションを返す。"""
        if self._session is None:
            raise RuntimeError(
                "PostgresUnitOfWork のコンテキスト外ではセッションを取得できません。"
            )
        return self._session

    def ensure_active(self) -> None:
        """アプリケーション処理がこの Unit of Work 内で実行中か検証する。"""
        if self._session is None:
            raise RuntimeError(
                "PostgresUnitOfWork のコンテキスト外では実行できません。"
            )

    def record_version(
        self,
        aggregate_id: uuid.UUID,
        version: int,
        *,
        namespace: str,
    ) -> None:
        """読み込んだ行の世代を、保存時の期待値として覚える。

        ``namespace`` はテーブル名で、**既定値を置かない**。省略を許すと、
        渡し忘れた経路だけが別の名前空間へ記録し、保存側が引くときに未読扱いに
        なる。さらに名前空間を空へ畳むと、別テーブルの同一 UUID で世代が混ざる
        ——``namespace`` を導入した理由そのものが戻ってくる。
        """
        self._loaded_versions[self._version_key(namespace, aggregate_id)] = version

    def remember_loaded_version(
        self,
        aggregate_id: uuid.UUID,
        version: int,
        *,
        namespace: str,
    ) -> None:
        """最初に読み込んだ世代を保持し、別世代の再読込で上書きしない。"""
        existing = self.loaded_version(aggregate_id, namespace=namespace)
        if existing is None:
            self.record_version(aggregate_id, version, namespace=namespace)

    def loaded_version(
        self,
        aggregate_id: uuid.UUID,
        *,
        namespace: str,
    ) -> int | None:
        """このトランザクションで読み込んだ世代を返す。未読なら ``None``。"""
        return self._loaded_versions.get(self._version_key(namespace, aggregate_id))

    async def __aenter__(self) -> Self:
        """セッションを開いてトランザクションを開始する。"""
        if self._session is not None:
            raise RuntimeError("PostgresUnitOfWork は二重に開始できません。")
        self._session = self._session_factory()
        self._loaded_versions.clear()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """未コミットの変更を必ず破棄し、セッションを閉じる。

        正常終了でも ``rollback()`` を呼ぶのは、``commit()`` を忘れた経路を
        「暗黙のロールバック」で静かに握り潰さないため。``commit()`` 済みなら
        この呼び出しは何もしない。
        """
        session = self._session
        if session is None:
            return
        try:
            await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._loaded_versions.clear()

    async def commit(self) -> None:
        """現在のトランザクションを確定する。"""
        await self.session.commit()

    async def rollback(self) -> None:
        """現在のトランザクションを取り消す。"""
        await self.session.rollback()
        self._loaded_versions.clear()


__all__ = [
    "PostgresConfigurationError",
    "PostgresSettings",
    "PostgresUnitOfWork",
    "create_async_engine_from_settings",
    "create_session_factory",
]
