"""PostgreSQL を使う Infrastructure の公開窓口。

接続、Repository、Composition Root をこのパッケージにまとめる。``repositories``
サブパッケージは永続化の実装、その他のモジュールは接続またはユースケースの
組み立てを担当する。
"""

from app.infrastructure.postgres.clinical import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
)
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
from app.infrastructure.postgres.medicine_catalog import MedicineCatalogUseCases
from app.infrastructure.postgres.organization import (
    CorporateUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.infrastructure.postgres.patient_care import (
    CoverageUseCases,
    PatientUseCases,
    ReceptionUseCases,
)
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    closed_date_range_matches,
    constraint_name,
)
from app.infrastructure.postgres.root import (
    PostgresCompositionRoot,
    PostgresRequestScope,
    PostgresUseCaseRegistry,
)
from app.infrastructure.postgres.schema import metadata

__all__ = [
    "AggregateMapping",
    "CorporateUseCases",
    "CoverageUseCases",
    "DispensingUseCases",
    "MedicationHistoryUseCases",
    "MedicineCatalogUseCases",
    "PatientUseCases",
    "PersistenceMappingError",
    "PostgresCompositionRoot",
    "PostgresConfigurationError",
    "PostgresRepositoryBase",
    "PostgresRepositorySet",
    "PostgresRequestScope",
    "PostgresSettings",
    "PostgresUnitOfWork",
    "PostgresUseCaseRegistry",
    "PrescriptionUseCases",
    "ReceptionUseCases",
    "StaffUseCases",
    "StoreUseCases",
    "closed_date_range_matches",
    "constraint_name",
    "create_async_engine_from_settings",
    "create_session_factory",
    "decode_aggregate",
    "encode_aggregate",
    "metadata",
]
