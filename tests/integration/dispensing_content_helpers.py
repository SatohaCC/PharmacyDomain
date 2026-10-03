"""調剤薬品対応の実DB試験で共通に使う永続化状態の読取。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def snapshot_dispensing_persistence(
    engine: AsyncEngine,
) -> dict[str, list[dict[str, object]]]:
    """別接続から原本・調剤の全行と監査を読み、payloadと検索列・世代を含める。"""
    snapshot: dict[str, list[dict[str, object]]] = {}
    async with engine.connect() as connection:
        for table in ("prescriptions", "dispensing_processes", "operation_audits"):
            result = await connection.execute(
                text(f"SELECT * FROM {table} ORDER BY id")
            )
            snapshot[table] = [dict(row) for row in result.mappings()]
    return snapshot
