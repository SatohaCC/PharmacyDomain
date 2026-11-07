"""NSIPS取込台帳RepositoryのPostgreSQLアダプタ。"""

from __future__ import annotations

import contextlib
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult

from app.application.integration.boundary_models import (
    NsipsFileRecord,
    NsipsFileStatus,
    NsipsOperation,
)
from app.application.integration.interfaces.nsips_file_repository import (
    NsipsFileRepository,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import nsips_files


def _row_to_record(row: Any) -> NsipsFileRecord:
    target_rec_id = (
        ReceptionId.parse(row.target_reception_id)
        if row.target_reception_id is not None
        else None
    )
    return NsipsFileRecord(
        id=row.id,
        corporate_id=CorporateId(row.corporate_id),
        store_id=StoreId(row.store_id),
        file_id=row.file_id,
        file_name=row.file_name,
        operation=NsipsOperation(row.operation),
        status=NsipsFileStatus(row.status),
        received_at=row.received_at,
        payload_fingerprint=row.payload_fingerprint or "",
        raw_payload=row.raw_payload or "",
        target_reception_id=target_rec_id,
        processed_at=row.processed_at,
        error_text=row.error_text or "",
    )


def _build_values(ledger: NsipsFileRecord) -> dict[str, Any]:
    now = ledger.received_at
    return {
        "id": ledger.id,
        "corporate_id": ledger.corporate_id.value,
        "store_id": ledger.store_id.value,
        "file_id": ledger.file_id,
        "file_name": ledger.file_name,
        "operation": ledger.operation.value,
        "status": ledger.status.value,
        "received_at": ledger.received_at,
        "payload_fingerprint": ledger.payload_fingerprint,
        "raw_payload": ledger.raw_payload,
        "target_reception_id": ledger.target_reception_id.value
        if ledger.target_reception_id is not None
        else None,
        "processed_at": ledger.processed_at,
        "error_text": ledger.error_text,
        "payload": {},
        "version": 1,
        "created_at": now,
        "updated_at": ledger.processed_at or now,
    }


class PostgresNsipsFileRepository(PostgresRepositoryBase, NsipsFileRepository):
    """NSIPS取込台帳をPostgreSQLへ保存するRepository。"""

    async def get_by_identity(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
        operation: NsipsOperation,
    ) -> NsipsFileRecord | None:
        """同一調剤・同一操作の台帳エントリを取得する。"""
        stmt = select(nsips_files).where(
            nsips_files.c.corporate_id == corporate_id.value,
            nsips_files.c.store_id == store_id.value,
            nsips_files.c.file_id == file_id,
            nsips_files.c.operation == operation.value,
        )
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        if row is None:
            return None
        return _row_to_record(row)

    async def get_applied_by_file_id(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        file_id: str,
    ) -> NsipsFileRecord | None:
        """指定された file_id で適用済みの登録・一括台帳エントリを取得する。"""
        stmt = select(nsips_files).where(
            nsips_files.c.corporate_id == corporate_id.value,
            nsips_files.c.store_id == store_id.value,
            nsips_files.c.file_id == file_id,
            nsips_files.c.status == NsipsFileStatus.APPLIED.value,
        )
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        if row is None:
            return None
        return _row_to_record(row)

    async def reserve(self, ledger: NsipsFileRecord) -> NsipsFileRecord | None:
        """ファイル取込を予約する。既に同一操作のエントリが存在すれば既存レコードを返し、新規予約できた場合は None を返す。"""
        values = _build_values(ledger)
        stmt = insert(nsips_files).values(**values)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_nsips_files_identity",
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        if result.rowcount == 0:
            return await self.get_by_identity(
                corporate_id=ledger.corporate_id,
                store_id=ledger.store_id,
                file_id=ledger.file_id,
                operation=ledger.operation,
            )
        return None

    async def _execute_save(self, session: Any, ledger: NsipsFileRecord) -> None:
        values = _build_values(ledger)
        stmt = insert(nsips_files).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_nsips_files_identity",
            set_={
                "status": values["status"],
                "payload_fingerprint": values["payload_fingerprint"],
                "raw_payload": values["raw_payload"],
                "target_reception_id": values["target_reception_id"],
                "processed_at": values["processed_at"],
                "error_text": values["error_text"],
                "updated_at": values["updated_at"],
            },
        )
        await session.execute(stmt)

    async def save(self, ledger: NsipsFileRecord) -> None:
        """台帳エントリを保存する。"""
        await self._execute_save(self.session, ledger)

    async def save_failed(self, ledger: NsipsFileRecord) -> None:
        """失敗した台帳エントリを独立したトランザクションで確実に永続化する。"""
        with contextlib.suppress(Exception):
            await self._unit_of_work.rollback()

        session_factory = getattr(self._unit_of_work, "_session_factory", None)
        if session_factory is not None:
            async with session_factory() as session:
                await self._execute_save(session, ledger)
                await session.commit()
        else:
            await self.save(ledger)


__all__ = ["PostgresNsipsFileRepository"]
