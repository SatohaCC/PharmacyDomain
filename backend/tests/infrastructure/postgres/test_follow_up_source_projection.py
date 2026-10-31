"""関連Event候補のSQLがメタデータだけを店舗読取範囲内で読む契約を固定する。"""

from datetime import date
from typing import Any, cast

from sqlalchemy import Select

from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.identifiers import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.store.identifiers import StoreId
from app.infrastructure.care_event.postgres.care_event import PostgresEventRepository
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.read_scope import RepositoryReadScope
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


class _CapturingUnitOfWork:
    """Postgres RepositoryにSQL実行セッションと店舗読取範囲を渡す。"""

    def __init__(self, corporate_id: CorporateId, store_id: StoreId) -> None:
        self.read_scope = RepositoryReadScope(
            corporate_id.value,
            (store_id.value,),
            date(2026, 9, 20),
            AccountPersonId.generate().value,
            UserAccountId.generate().value,
            selected_store_ids=(store_id.value,),
        )
        self.session = _CapturingSession()


async def test_tc45_46_候補SQLは法人患者と選択店舗で絞り本文payloadを読まない() -> None:
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    unit_of_work = _CapturingUnitOfWork(corporate_id, store_id)
    repository = PostgresEventRepository(cast(PostgresUnitOfWork, unit_of_work))

    await repository.list_related_candidates(
        corporate_id=corporate_id, patient_id=PatientId.generate()
    )

    statement = unit_of_work.session.statement
    assert statement is not None
    compiled = compiled_sql(statement)
    assert "care_events.corporate_id" in compiled
    assert "care_events.patient_id" in compiled
    assert "care_events.store_id IN" in compiled
    assert "care_events.event_type_name" in compiled
    assert "care_events.occurred_at" in compiled
    assert "care_events.created_at" in compiled
    assert "care_events.payload" not in compiled
    assert "medication_history_records" not in compiled
