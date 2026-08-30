"""PostgreSQL接続設定の読み込みを検査する。"""

from __future__ import annotations

import pytest

from app.infrastructure.postgres.settings import (
    PostgresConfigurationError,
    PostgresSettings,
)


def test_同期用URLが_asyncpg用へ正規化される() -> None:
    """運用ツールが配る postgresql:// をそのまま渡しても動く。"""
    # Arrange
    environment = {"DATABASE_URL": "postgresql://user:pass@host:5432/db"}

    # Act
    settings = PostgresSettings.from_environment(environment)

    # Assert
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_postgresスキームも_asyncpg用へ正規化される() -> None:
    """一部のホスティングは postgres:// を配る。"""
    # Arrange
    environment = {"DATABASE_URL": "postgres://user:pass@host:5432/db"}

    # Act
    settings = PostgresSettings.from_environment(environment)

    # Assert
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_DATABASE_URLが無いと_設定エラーになる() -> None:
    """接続先不明のまま起動すると、最初のリクエストまで失敗が遅れる。"""
    # Arrange
    environment: dict[str, str] = {}

    # Act & Assert
    with pytest.raises(PostgresConfigurationError):
        PostgresSettings.from_environment(environment)


def test_PostgreSQL以外のURLは_設定エラーになる() -> None:
    """方言が違うURLは、接続時ではなく設定読み込み時に落とす。"""
    # Arrange
    environment = {"DATABASE_URL": "mysql://user:pass@host/db"}

    # Act & Assert
    with pytest.raises(PostgresConfigurationError):
        PostgresSettings.from_environment(environment)


def test_プール設定が_環境変数から読める() -> None:
    """既定値のままでは負荷に合わせられない。"""
    # Arrange
    environment = {
        "DATABASE_URL": "postgresql://user:pass@host/db",
        "POSTGRES_POOL_SIZE": "20",
        "POSTGRES_MAX_OVERFLOW": "0",
        "POSTGRES_POOL_TIMEOUT": "5.5",
        "POSTGRES_COMMAND_TIMEOUT": "3",
    }

    # Act
    settings = PostgresSettings.from_environment(environment)

    # Assert
    assert settings.pool_size == 20
    assert settings.max_overflow == 0
    assert settings.pool_timeout == 5.5
    assert settings.command_timeout == 3.0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("POSTGRES_POOL_SIZE", "0"),
        ("POSTGRES_POOL_SIZE", "文字列"),
        ("POSTGRES_MAX_OVERFLOW", "-1"),
        ("POSTGRES_POOL_TIMEOUT", "0"),
        ("POSTGRES_COMMAND_TIMEOUT", "-2"),
    ],
)
def test_不正なプール設定は_設定エラーになる(key: str, value: str) -> None:
    """黙って既定値へ落とすと、設定したつもりの値が効かない。"""
    # Arrange
    environment = {"DATABASE_URL": "postgresql://user:pass@host/db", key: value}

    # Act & Assert
    with pytest.raises(PostgresConfigurationError):
        PostgresSettings.from_environment(environment)


def test_空文字の設定は_既定値になる() -> None:
    """未設定と空文字を区別しても、運用上の意味が無い。"""
    # Arrange
    environment = {
        "DATABASE_URL": "postgresql://user:pass@host/db",
        "POSTGRES_POOL_SIZE": "",
    }

    # Act
    settings = PostgresSettings.from_environment(environment)

    # Assert
    assert settings.pool_size == 5
