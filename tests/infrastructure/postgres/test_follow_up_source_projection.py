"""候補検索SQLが本文列を読まずに条件を適用することを固定する。"""

from typing import Any, cast

from sqlalchemy import Select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.medication_history import (
    PostgresMedicationHistoryRepository,
)
from tests.infrastructure.postgres.helpers import compiled_sql


class _MappingRows:
    """空のSQL結果を返す。"""

    def mappings(self) -> _MappingRows:
        return self

    def all(self) -> list[dict[str, object]]:
        return []

    def one_or_none(self) -> None:
        return None


class _CapturingSession:
    """Repositoryが実行したSQLAlchemy文を記録する。"""

    def __init__(self) -> None:
        self.statement: Select[Any] | None = None

    async def execute(self, statement: Select[Any]) -> _MappingRows:
        self.statement = statement
        return _MappingRows()


class _CapturingUnitOfWork:
    """Postgres RepositoryにSQL実行セッションを渡す。"""

    def __init__(self) -> None:
        self.read_scope = None
        self.session = _CapturingSession()


async def test_tc25_候補SQLは法人患者確定条件を持ち本文payloadを選択しない() -> None:
    unit_of_work = _CapturingUnitOfWork()
    repository = PostgresMedicationHistoryRepository(
        cast(PostgresUnitOfWork, unit_of_work)
    )

    await repository.list_confirmed_sources(
        corporate_id=CorporateId.generate(), patient_id=PatientId.generate()
    )

    statement = unit_of_work.session.statement
    assert statement is not None
    compiled = compiled_sql(statement)
    assert "medication_history_records.corporate_id" in compiled
    assert "medication_history_records.patient_id" in compiled
    assert "medication_history_records.status" in compiled
    assert "payload" not in compiled
    assert "soap" not in compiled
    assert "profile_updates" not in compiled
