"""成功した業務更新を本人の操作として監査する。"""

from datetime import UTC, datetime

import pytest

from app.application.common.audit import AuditedOperation, OperationAudit
from tests.fakes.in_memory_audit_repository import InMemoryAuditRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork


def _entry() -> OperationAudit:
    return OperationAudit(
        person_id="本人",
        account_id="個人アカウント",
        operation="店舗名変更",
        resource_id="店舗",
        corporate_id="法人",
        store_id="店舗",
        recorded_at=datetime(2026, 9, 17, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_業務成功後に本人と対象の監査を保存する() -> None:
    repository = InMemoryAuditRepository()
    executed: list[str] = []

    async def update() -> str:
        assert repository.entries == []
        executed.append("更新")
        return "保存結果"

    entry = _entry()
    actual = await AuditedOperation(repository, NullUnitOfWork()).execute(update, entry)

    assert actual == "保存結果"
    assert executed == ["更新"]
    assert repository.entries == [entry]


@pytest.mark.asyncio
async def test_業務失敗時は成功監査を保存しない() -> None:
    repository = InMemoryAuditRepository()

    async def update() -> None:
        raise RuntimeError("業務更新障害")

    with pytest.raises(RuntimeError, match="業務更新障害"):
        await AuditedOperation(repository, NullUnitOfWork()).execute(update, _entry())
    assert repository.entries == []


@pytest.mark.asyncio
async def test_監査保存失敗をトランザクション境界へ伝播する() -> None:
    repository = InMemoryAuditRepository(fail=True)

    async def update() -> str:
        return "更新済み"

    with pytest.raises(RuntimeError, match="監査保存障害"):
        await AuditedOperation(repository, NullUnitOfWork()).execute(update, _entry())
