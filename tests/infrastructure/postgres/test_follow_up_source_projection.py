"""関連Event候補のSQLがメタデータだけを店舗横断で読む契約を固定する。"""

from typing import Any, cast

from sqlalchemy import Select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.care_event import PostgresEventRepository
from tests.infrastructure.postgres.helpers import compiled_sql


class _MappingRows:
    """空のSQL結果を返す。"""

    def mappings(self) -> _MappingRows:
        return self

    def all(self) -> list[dict[str, object]]:
        return []


class _CapturingSession:
    """Repositoryが実行したSQLAlchemy文を記録する。"""

    def __init__(self) -> None:
        self.statement: Select[Any] | None = None

    async def execute(self, statement: Select[Any]) -> _MappingRows:
        self.statement = statement
        return _MappingRows()


class _RejectingReadScope:
    """候補SQLが通常の店舗読取Scopeを通らないことを確かめる。"""

    def apply(self, *_args: object) -> Select[Any]:
        raise AssertionError("候補メタデータの検索へ通常の店舗Scopeを適用しました")


class _CapturingUnitOfWork:
    """Postgres RepositoryにSQL実行セッションを渡す。"""

    def __init__(self) -> None:
        self.read_scope = _RejectingReadScope()
        self.session = _CapturingSession()


async def test_tc45_46_候補SQLは法人患者で絞り本文payloadを読まない() -> None:
    unit_of_work = _CapturingUnitOfWork()
    repository = PostgresEventRepository(cast(PostgresUnitOfWork, unit_of_work))

    await repository.list_related_candidates(
        corporate_id=CorporateId.generate(), patient_id=PatientId.generate()
    )

    statement = unit_of_work.session.statement
    assert statement is not None
    compiled = compiled_sql(statement)
    assert "care_events.corporate_id" in compiled
    assert "care_events.patient_id" in compiled
    assert "care_events.event_type_name" in compiled
    assert "care_events.occurred_at" in compiled
    assert "care_events.created_at" in compiled
    assert "care_events.payload" not in compiled
    assert "medication_history_records" not in compiled
    assert "care_events.c.store_id IN" not in compiled
