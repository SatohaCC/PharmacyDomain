"""監査の追記結果と障害を観測するFake。"""

from app.application.common.audit import AuditRepository, OperationAudit


class InMemoryAuditRepository(AuditRepository):
    """追記された監査を保持する。"""

    def __init__(self, *, fail: bool = False) -> None:
        self.entries: list[OperationAudit] = []
        self.fail = fail

    async def append(self, entry: OperationAudit) -> None:
        if self.fail:
            raise RuntimeError("監査保存障害")
        self.entries.append(entry)
