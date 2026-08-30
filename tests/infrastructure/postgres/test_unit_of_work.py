"""PostgreSQL Unit of Work のトランザクション境界を検査する。"""

from __future__ import annotations

import uuid

import pytest

from tests.fakes.recording_async_session import RecordingAsyncSession
from tests.infrastructure.postgres.helpers import create_unit_of_work


async def test_コンテキスト外では_セッションを取得できない() -> None:
    """開始前のセッション利用は、トランザクション外の書き込みになる。"""
    # Arrange
    unit_of_work = create_unit_of_work(RecordingAsyncSession())

    # Act & Assert
    with pytest.raises(RuntimeError):
        _ = unit_of_work.session


async def test_二重に開始すると_失敗する() -> None:
    """同じインスタンスの並行利用はセッションを壊すので、気づける形で落とす。"""
    # Arrange
    unit_of_work = create_unit_of_work(RecordingAsyncSession())

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(RuntimeError):
            await unit_of_work.__aenter__()


async def test_commitせずに抜けると_巻き戻して閉じる() -> None:
    """暗黙のロールバックに任せると、commit忘れが無言のデータ消失になる。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)

    # Act
    async with unit_of_work:
        pass

    # Assert
    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closed == 1


async def test_commitして抜けると_セッションを閉じる() -> None:
    """確定後の巻き戻し呼び出しは何もしないので、閉じる経路は1本でよい。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)

    # Act
    async with unit_of_work:
        await unit_of_work.commit()

    # Assert
    assert session.commits == 1
    assert session.closed == 1


async def test_例外で抜けると_巻き戻して閉じる() -> None:
    """途中で失敗した書き込みを残さない。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)

    # Act
    with pytest.raises(ValueError):
        async with unit_of_work:
            raise ValueError("業務処理の失敗")

    # Assert
    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closed == 1


async def test_記録した世代が_トランザクション終了で破棄される() -> None:
    """前のトランザクションの世代を持ち越すと、他人の更新を上書きしうる。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)
    aggregate_id = uuid.uuid4()

    # Act
    async with unit_of_work:
        unit_of_work.record_version(aggregate_id, 5)
        assert unit_of_work.loaded_version(aggregate_id) == 5

    # Assert
    assert unit_of_work.loaded_version(aggregate_id) is None


async def test_巻き戻すと_記録した世代を破棄する() -> None:
    """巻き戻した読み取りの世代を残すと、次の保存が誤った前提で走る。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)
    aggregate_id = uuid.uuid4()

    # Act
    async with unit_of_work:
        unit_of_work.record_version(aggregate_id, 2)
        await unit_of_work.rollback()

        # Assert
        assert unit_of_work.loaded_version(aggregate_id) is None
