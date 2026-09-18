"""業務更新と同じトランザクションに保存する監査契約。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.common import UnitOfWork


@dataclass(frozen=True, kw_only=True)
class OperationAudit:
    """秘密や本文を含めない操作主体と対象の記録。"""

    person_id: str
    account_id: str
    operation: str
    resource_id: str
    recorded_at: datetime
    corporate_id: str | None = None
    store_id: str | None = None


class AuditRepository(Protocol):
    """監査を追記するだけの保存境界。"""

    async def append(self, entry: OperationAudit) -> None:
        """現在のUoW内で監査を追記する。"""
        ...


class AuditedOperation:
    """業務成功後に監査を保存し、失敗をUoWへ伝播する。"""

    def __init__(self, repository: AuditRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute[T](
        self, operation: Callable[[], Awaitable[T]], entry: OperationAudit
    ) -> T:
        """更新と監査を同じUoW内で行い、結果を返す。"""
        self._unit_of_work.ensure_active()
        result = await operation()
        await self._repository.append(entry)
        return result
