"""`UnitOfWork` のテスト用実装。"""

from __future__ import annotations

from app.application.common import UnitOfWork


class NullUnitOfWork(UnitOfWork):
    """トランザクション境界を持たない経路へ渡す、何もしない実行中境界。

    インメモリのリポジトリは複数集約の書き込みを原子的にまとめられないため、
    ``ensure_active()`` に検証させる対象がそもそも存在しない。ユースケース側が
    ``UnitOfWork`` を必須依存にしている意図は「渡し忘れを型検査で落とす」ことに
    あるので、テストでは黙って何もしない実装を明示的に渡す。
    """

    def ensure_active(self) -> None:
        """常に成功する。検証すべき境界を持たないため何もしない。"""
