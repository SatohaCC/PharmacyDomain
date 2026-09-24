"""医薬品マスタ実データ（YJコードリストCSV）を一括インポートするCLIツール。

``uv run python -m tools.import_medicine_catalog`` で実行し、接続先は ``DATABASE_URL`` で
指定する。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from app.application.access_control.models import ActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.medicine_catalog.import_yj_catalog import (
    ImportYjCatalogCommand,
    ImportYjCatalogUseCase,
)
from app.infrastructure.postgres.connection import (
    PostgresSettings,
    PostgresUnitOfWork,
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)

DEFAULT_CSV_PATH = (
    Path("docs") / "references" / "個別医薬品コード(YJコード)リスト_202608_20260815.csv"
)
DEFAULT_CATALOG_VERSION = date(2026, 8, 15)


def load_settings(environment: Mapping[str, str] | None = None) -> PostgresSettings:
    """投入先の接続設定を読み込む。"""
    return PostgresSettings.from_environment(environment)


def _vendor_auth() -> AuthorizationService:
    """インポート実行用のベンダーシステム管理者認可。"""
    return AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="cli-import-tool")
    )


async def run_import(
    file_path: Path,
    catalog_version: date,
    chunk_size: int,
    environment: Mapping[str, str] | None = None,
) -> None:
    """CSVファイルを読み込み、PostgreSQLに一括保存する。"""
    if not file_path.exists():
        print(f"エラー: 指定されたファイルが存在しません: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"インポート開始: {file_path}")
    print(f"カタログ版: {catalog_version}, チャンクサイズ: {chunk_size}")

    start_time = time.monotonic()
    settings = load_settings(environment)
    engine = create_async_engine_from_settings(settings)

    try:
        async with PostgresUnitOfWork(create_session_factory(engine)) as work:
            repositories = PostgresRepositorySet.create(work)
            use_case = ImportYjCatalogUseCase(
                repositories.medicine_catalog,
                _vendor_auth(),
                chunk_size=chunk_size,
            )
            result = await use_case.execute(
                ImportYjCatalogCommand(
                    file_path=str(file_path),
                    catalog_version=catalog_version,
                )
            )
            await work.commit()

        elapsed = time.monotonic() - start_time
        print(
            f"インポート完了: 総行数={result.total_rows}, "
            f"保存件数={result.imported_count}, 所要時間={elapsed:.2f}秒"
        )
    finally:
        await engine.dispose()


def main() -> None:
    """コマンドライン引数を解釈してインポートを実行する。"""
    parser = argparse.ArgumentParser(
        description="医薬品マスタ（YJコードリストCSV）を一括インポートするCLIツール"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"インポート対象のCSVファイルパス（既定: {DEFAULT_CSV_PATH}）",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_CATALOG_VERSION.isoformat(),
        help=f"カタログ版年月日（YYYY-MM-DD、既定: {DEFAULT_CATALOG_VERSION.isoformat()}）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="1回の一括保存で処理する件数（既定: 1000）",
    )

    args = parser.parse_args()
    catalog_version = date.fromisoformat(args.version)

    asyncio.run(
        run_import(
            file_path=args.file,
            catalog_version=catalog_version,
            chunk_size=args.chunk_size,
        )
    )


if __name__ == "__main__":
    main()
