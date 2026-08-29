"""PostgreSQL 接続設定。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


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
