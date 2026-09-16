"""Production Composition Root。

上から順に寿命が長くなる。``PostgresUseCaseRegistry`` は1スコープで実行できる
操作のレジストリ（アクセス時にオンデマンドで生成）、``PostgresRequestScope`` は
1リクエスト（=1トランザクション）分の実行文脈、``PostgresCompositionRoot`` は
プロセス全体の入口である。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.composition.system_clock import SystemUtcClock
from app.application.corporate.corporate_access import CorporateAccessService
from app.infrastructure.di.registry import PostgresUseCaseRegistry
from app.infrastructure.postgres.connection import (
    PostgresSettings,
    PostgresUnitOfWork,
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.repositories import PostgresRepositorySet

# --------------------------------------------------------------------------
# 1リクエスト分の実行文脈
# --------------------------------------------------------------------------


class PostgresRequestScope:
    """1リクエスト（=1トランザクション）分の実行文脈。

    **トランザクションの開始・確定はここ1箇所にある。** 複数集約を書き込む
    ユースケースには同じ UnitOfWork を必須依存として渡すが、ユースケース自身は
    境界を開きも閉じもしない。実行時に開始済みであることだけを検証する。

    書き込みの取りこぼしも構造で防いでいる。``PostgresUnitOfWork`` はコンテキスト
    の外でセッションを渡さないので、スコープを開かずに Repository を呼ぶと
    ``RuntimeError`` になる。「境界を張り忘れたまま保存が成功する」経路は無い。

    ``AsyncSession`` は並行実行安全ではないため、このインスタンスは
    リクエストをまたいで使い回さない。
    """

    def __init__(
        self,
        unit_of_work: PostgresUnitOfWork,
        *,
        authorization: AuthorizationService,
        clock: Clock,
    ) -> None:
        self._unit_of_work = unit_of_work
        repositories = PostgresRepositorySet.create(unit_of_work)
        corporate_access = CorporateAccessService(repositories.corporate, authorization)
        self._repositories = repositories
        self._use_cases = PostgresUseCaseRegistry(
            repositories,
            corporate_access,
            authorization=authorization,
            clock=clock,
            unit_of_work=unit_of_work,
        )

    @property
    def use_cases(self) -> PostgresUseCaseRegistry:
        """このスコープで実行できるユースケース一式を返す。"""
        return self._use_cases

    @property
    def repositories(self) -> PostgresRepositorySet:
        """このスコープの Repository 一式を返す。"""
        return self._repositories

    async def __aenter__(self) -> Self:
        """トランザクションを開始する。"""
        await self._unit_of_work.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """例外が無ければコミットし、あれば破棄して閉じる。

        コミットを呼び出し側の作法に委ねない。委ねると、``commit()`` を書き忘れた
        経路が「例外は出ないがデータが消える」振る舞いになる。コミット自体が
        失敗した場合も、``finally`` で Unit of Work を閉じてから例外を伝える。
        """
        try:
            if exc_type is None:
                await self._unit_of_work.commit()
        finally:
            await self._unit_of_work.__aexit__(exc_type, exc_value, traceback)


# --------------------------------------------------------------------------
# プロセス全体の入口
# --------------------------------------------------------------------------


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
        """
        engine = create_async_engine_from_settings(settings)
        session_factory = create_session_factory(engine)
        actual_clock = SystemUtcClock() if clock is None else clock
        return cls(
            engine=engine,
            session_factory=session_factory,
            clock=actual_clock,
        )

    def request_scope(
        self,
        *,
        authorization: AuthorizationService,
    ) -> PostgresRequestScope:
        """1リクエスト（=1トランザクション）分の実行スコープを生成する。"""
        return PostgresRequestScope(
            PostgresUnitOfWork(self.session_factory),
            authorization=authorization,
            clock=self.clock,
        )

    async def dispose(self) -> None:
        """プロセスの終了時にコネクションプールを破棄する。"""
        await self.engine.dispose()

    async def close(self) -> None:
        """プロセスの終了時にコネクションプールを破棄する。"""
        await self.dispose()


__all__ = [
    "PostgresCompositionRoot",
    "PostgresRequestScope",
]
