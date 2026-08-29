"""Production Composition Root。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.system_clock import SystemUtcClock
from app.infrastructure.composition.scope import PostgresRequestScope
from app.infrastructure.postgres.engine import (
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.settings import PostgresSettings
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


@dataclass(frozen=True, slots=True)
class PostgresCompositionRoot:
    """PostgreSQL アダプタを組み立てる唯一の入口。

    プロセスの寿命を持つのはエンジンとセッションファクトリだけで、Repository も
    ユースケースもリクエストごとに作り直す。``AsyncSession`` は並行実行安全では
    ないため、使い回すと同時実行で壊れる。
    """

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    clock: Clock

    @classmethod
    def from_settings(
        cls,
        settings: PostgresSettings,
        *,
        clock: Clock | None = None,
    ) -> Self:
        """設定から Composition Root を生成する。

        業務処理へ渡す現在時刻の供給元も**ここでだけ**選ぶ。``SystemUtcClock`` は
        ``datetime.now(UTC)`` を呼ぶ唯一の場所であり、Domain / Application が
        暗黙に「今」を読むことを禁じた規則（ruff の ``DTZ``）の逃げ道にしない。
        行の監査時刻（``created_at`` / ``updated_at``）は Repository が
        PostgreSQL の UTC 時刻関数で統一する。
        """
        engine = create_async_engine_from_settings(settings)
        return cls(
            engine=engine,
            session_factory=create_session_factory(engine),
            clock=clock if clock is not None else SystemUtcClock(),
        )

    def request_scope(
        self,
        *,
        authorization: AuthorizationService,
    ) -> PostgresRequestScope:
        """1リクエスト分のトランザクションとユースケース一式を組み立てる。

        ``authorization`` は認証基盤が生成した信頼済みの ``ActorContext`` を
        包んだもので、HTTP 入力から組み立ててはならない。
        """
        return PostgresRequestScope(
            PostgresUnitOfWork(self.session_factory),
            authorization=authorization,
            clock=self.clock,
        )

    async def dispose(self) -> None:
        """接続プールを解放する。"""
        await self.engine.dispose()
