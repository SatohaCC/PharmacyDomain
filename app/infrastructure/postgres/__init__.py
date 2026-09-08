"""PostgreSQL を使う Infrastructure の公開窓口。

接続、スキーマ、および Repository をこのパッケージにまとめる。``repositories``
サブパッケージは永続化の実装、その他のモジュールは接続またはマッピングを担当する。
"""

from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.connection import (
    PostgresConfigurationError,
    PostgresSettings,
    PostgresUnitOfWork,
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    closed_date_range_matches,
    constraint_name,
)
from app.infrastructure.postgres.schema import metadata

__all__ = [
    "AggregateMapping",
    "PersistenceMappingError",
    "PostgresConfigurationError",
    "PostgresRepositoryBase",
    "PostgresRepositorySet",
    "PostgresSettings",
    "PostgresUnitOfWork",
    "closed_date_range_matches",
    "constraint_name",
    "create_async_engine_from_settings",
    "create_session_factory",
    "decode_aggregate",
    "encode_aggregate",
    "metadata",
]
