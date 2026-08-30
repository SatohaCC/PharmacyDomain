"""発行されたSQLを記録する、DBに繋がないセッションのテストダブル。

PostgreSQL Repository の分岐（新規登録か更新か、楽観ロックの条件、制約違反の
写像）は、実DBが無くても「どんな文を組み立てたか」と「何行に当たったか」で
固定できる。実DBを要求すると検査がCIから外れ、結局誰も回さなくなる。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Self


class FakeResult:
    """``AsyncSession.execute()`` の戻り値のうち、Repositoryが使う部分だけ。"""

    def __init__(
        self,
        *,
        rows: Sequence[Mapping[str, object]] = (),
        rowcount: int = 1,
        scalar: object = None,
    ) -> None:
        self._rows = list(rows)
        self.rowcount = rowcount
        self._scalar = scalar

    def mappings(self) -> Self:
        """行を辞書として読む入口。自身を返す。"""
        return self

    def one_or_none(self) -> Mapping[str, object] | None:
        """0件なら ``None``、1件ならその行を返す。"""
        if not self._rows:
            return None
        if len(self._rows) > 1:
            raise AssertionError("1行を期待した検索が複数行を返しました。")
        return self._rows[0]

    def all(self) -> list[Mapping[str, object]]:
        """全行を返す。"""
        return list(self._rows)

    def scalar_one_or_none(self) -> object:
        """先頭列の値を返す。"""
        return self._scalar


class RecordingAsyncSession:
    """実行されたstatementを順に記録し、あらかじめ渡した結果を返す。"""

    def __init__(self, *, results: Sequence[FakeResult] = ()) -> None:
        self.executed: list[Any] = []
        self._results = list(results)
        self.error: Exception | None = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    async def commit(self) -> None:
        """確定回数を数える。"""
        self.commits += 1

    async def rollback(self) -> None:
        """巻き戻し回数を数える。"""
        self.rollbacks += 1

    async def close(self) -> None:
        """クローズ回数を数える。"""
        self.closed += 1

    async def execute(self, statement: Any) -> FakeResult:
        """statementを記録し、次の結果を返す。"""
        self.executed.append(statement)
        if self.error is not None:
            raise self.error
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    @property
    def last_statement(self) -> Any:
        """直近に実行したstatement。"""
        if not self.executed:
            raise AssertionError("statementが1つも実行されていません。")
        return self.executed[-1]
