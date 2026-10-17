"""法人ロックのSQLとトランザクション境界の検証。"""

from typing import Any

import pytest

from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from tests.fakes.recording_async_session import RecordingAsyncSession
from tests.infrastructure.postgres.helpers import create_unit_of_work


@pytest.mark.asyncio
async def test_法人ロック_キーをバインドしてトランザクション単位で取得し_確定を呼び出し側へ委ねる() -> (
    None
):
    # Arrange
    session = RecordingAsyncSession()
    work = create_unit_of_work(session)
    key = "corporate:検証'法人"

    # Act
    async with work:
        await PostgresOrganizationLock(work).acquire(key)
        statement: Any = session.last_statement
        compiled = statement.compile()

        # Assert
        assert "pg_advisory_xact_lock" in str(compiled)
        assert "hashtextextended" in str(compiled)
        assert key not in str(compiled)
        assert key in compiled.params.values()
        assert session.commits == 0
