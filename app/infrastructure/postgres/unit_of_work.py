"""PostgreSQL 用 Unit of Work 実装。"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


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
            raise RuntimeError("PostgresUnitOfWork のコンテキスト外では実行できません。")

    def record_version(
        self,
        aggregate_id: uuid.UUID,
        version: int,
        *,
        namespace: str = "",
    ) -> None:
        """読み込んだ行の世代を、保存時の期待値として覚える。

        ``namespace`` を省略した呼び出しは低レベル契約との互換性を保つ。
        Repository はテーブル名を必ず渡す。
        """
        self._loaded_versions[self._version_key(namespace, aggregate_id)] = version

    def remember_loaded_version(
        self,
        aggregate_id: uuid.UUID,
        version: int,
        *,
        namespace: str = "",
    ) -> None:
        """最初に読み込んだ世代を保持し、別世代の再読込で上書きしない。"""
        existing = self.loaded_version(aggregate_id, namespace=namespace)
        if existing is None:
            self.record_version(aggregate_id, version, namespace=namespace)

    def loaded_version(
        self,
        aggregate_id: uuid.UUID,
        *,
        namespace: str = "",
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
