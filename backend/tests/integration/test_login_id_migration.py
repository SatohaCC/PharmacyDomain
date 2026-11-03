"""既存メールを勝手にIDへ変換せず、対応表で資格情報を保全する。"""

import importlib
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infrastructure.postgres.helpers import ordered_migrations


@pytest.mark.asyncio
async def test_ログインID移行_既存資格情報がある場合_対応表を要求しメールとパスワードを保持する(
    engine: AsyncEngine,
) -> None:
    # Arrange
    schema = "login_migration_" + uuid.uuid4().hex
    vendor = "01930000-0000-7000-8000-000000000002"
    corporate = "01930000-0000-7000-8000-000000000005"
    module = importlib.import_module("migrations.versions.20261102_0017_login_id")
    async with engine.begin() as connection:
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
        await connection.execute(text(f"SET LOCAL search_path TO {schema}, public"))

        def create_legacy(sync: Connection) -> None:
            context = MigrationContext.configure(sync)
            with Operations.context(context):
                for migration in ordered_migrations():
                    if migration.revision == "20261102_0017":
                        break
                    migration.upgrade()

        await connection.run_sync(create_legacy)
        await connection.execute(
            text("""INSERT INTO corporates
            (id, name, representative_name, status, payload, version, created_at, updated_at)
            VALUES (CAST(:id AS uuid), '移行検証法人', '検証担当', 'active', '{}'::jsonb, 1, now(), now())"""),
            {"id": corporate},
        )
        await connection.execute(
            text("""INSERT INTO vendor_operators
            (id, email, password_hash, external_subject, is_active)
            VALUES (CAST(:id AS uuid), 'shared@example.test', '既存の合成ハッシュ', 'vendor:migration', true)"""),
            {"id": vendor},
        )
        await connection.execute(
            text("""INSERT INTO local_credentials
            (corporate_id, email, subject, password_hash, must_change, failed_attempts)
            VALUES (CAST(:id AS uuid), 'shared@example.test', 'local:migration', '利用者の合成ハッシュ', true, 0)"""),
            {"id": corporate},
        )
        await connection.execute(
            text("""INSERT INTO local_sessions
            (digest, subject, restricted, expires_at)
            VALUES ('移行前の合成セッション', 'local:migration', true, now() + interval '1 hour')""")
        )

        def apply(sync: Connection, mapping: dict[str, str]) -> None:
            context = MigrationContext.configure(
                sync, opts={"login_id_mapping": mapping}
            )
            with Operations.context(context):
                module.upgrade()

        # Act / Assert: 未割当では列変更を始めない。
        with pytest.raises(RuntimeError, match="対応表が必要"):
            await connection.run_sync(lambda sync: apply(sync, {}))
        count = (
            await connection.execute(
                text("""SELECT count(*) FROM information_schema.columns
            WHERE table_schema=:schema AND table_name='local_credentials' AND column_name='login_id'"""),
                {"schema": schema},
            )
        ).scalar_one()
        assert count == 0
        await connection.run_sync(
            lambda sync: apply(
                sync,
                {
                    f"vendor:{vendor}": " Vendor-Admin ",
                    f"{corporate}:shared@example.test": "staff-001",
                },
            )
        )
        actual_vendor = (
            await connection.execute(
                text("SELECT login_id, email, password_hash FROM vendor_operators")
            )
        ).one()
        actual_staff = (
            await connection.execute(
                text("SELECT login_id, email, password_hash FROM local_credentials")
            )
        ).one()
        assert tuple(actual_vendor) == (
            "vendor-admin",
            "shared@example.test",
            "既存の合成ハッシュ",
        )
        assert tuple(actual_staff) == (
            "staff-001",
            "shared@example.test",
            "利用者の合成ハッシュ",
        )
        assert (
            await connection.execute(text("SELECT count(*) FROM local_sessions"))
        ).scalar_one() == 0
        await connection.execute(text("SET LOCAL search_path TO public"))
        await connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
