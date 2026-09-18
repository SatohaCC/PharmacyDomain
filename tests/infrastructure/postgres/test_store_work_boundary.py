"""閉局前の未完了業務の照会が、終端状態を集約側から引くことを固定する。

終端の一覧をSQL側へ文字列で書き写すと、状態を1つ足したときにその状態が黙って
「終端扱い」になり、未完了の業務を抱えた店舗を閉局できてしまう。実DBに繋ぐまで
誰も落ちないので、発行するSQLの形で確かめる。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingProcessStatus
from app.domain.prescription.primitives import PrescriptionStatus
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.organization import PostgresStoreWorkBoundary
from tests.fakes.recording_async_session import FakeResult, RecordingAsyncSession
from tests.infrastructure.postgres.helpers import create_unit_of_work

#: 終端に達したとみなす状態。集約側の ``is_terminal`` とは独立に書く。
#: 状態を足して終端の判断を誤ると、どちらか一方だけが変わって落ちる。
_TERMINAL_PRESCRIPTION = {PrescriptionStatus.DISPENSED, PrescriptionStatus.CANCELLED}
_TERMINAL_DISPENSING = {
    DispensingProcessStatus.COMPLETED,
    DispensingProcessStatus.CANCELLED,
}


async def _issued_sql() -> str:
    """未完了照会が実際に発行するSQLを、値を埋めた形で取り出す。"""
    session = RecordingAsyncSession(results=[FakeResult(scalar=False)])
    work = create_unit_of_work(session)
    async with work:
        boundary = PostgresStoreWorkBoundary(work)
        assert not await boundary.has_unfinished(
            CorporateId.generate(), StoreId.generate()
        )
    statement: Any = session.last_statement
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def _excluded_statuses(sql: str, column: str) -> set[str]:
    """``<列> NOT IN (...)`` に並ぶ値を取り出す。

    値だけを探すと、``cancelled`` のように処方箋と調剤で同じ文字列を持つ状態が
    どちらの句のものか区別できない。列名から始まる句を切り出して数える。
    """
    marker = f"{column} NOT IN ("
    start = sql.index(marker) + len(marker)
    end = sql.index(")", start)
    return {item.strip().strip("'") for item in sql[start:end].split(",")}


@pytest.mark.asyncio
async def test_除外するのは_集約が終端と定めた状態だけである() -> None:
    # Act
    sql = await _issued_sql()

    # Assert
    assert _excluded_statuses(sql, "prescriptions.status") == {
        status.value for status in _TERMINAL_PRESCRIPTION
    }
    assert _excluded_statuses(sql, "dispensing_processes.status") == {
        status.value for status in _TERMINAL_DISPENSING
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(PrescriptionStatus))
async def test_終端でない処方箋の状態は_未完了として数える(
    status: PrescriptionStatus,
) -> None:
    # Act
    excluded = _excluded_statuses(await _issued_sql(), "prescriptions.status")

    # Assert
    assert (status.value in excluded) is (status in _TERMINAL_PRESCRIPTION)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(DispensingProcessStatus))
async def test_終端でない調剤の状態は_未完了として数える(
    status: DispensingProcessStatus,
) -> None:
    # Act
    excluded = _excluded_statuses(await _issued_sql(), "dispensing_processes.status")

    # Assert
    assert (status.value in excluded) is (status in _TERMINAL_DISPENSING)
