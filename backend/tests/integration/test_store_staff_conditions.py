"""店舗別の勤務条件をHTTPから保存し、期間と訂正履歴を照会する。"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.composition.adapters.organization_snapshot_mapping import (
    staff_store_source,
)
from app.domain.staff.primitives import WeeklyContractHours
from app.domain.staff.services import StaffStoreAssignmentService
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.factories.store_factory import create_store
from tests.integration.organization_helpers import setup_organization
from tests.integration.test_local_authentication import local_app


@pytest.mark.asyncio
async def test_勤務条件登録_二店舗で異なる週時間数と同日訂正_再取得で履歴を保持する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    other = create_store(corporate_id=fixture.corporate.id, name="兼務先の店舗")
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.store.save(other)
        original = await repositories.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
        )
        assert original is not None
        staff = StaffStoreAssignmentService().assign_concurrent_store(
            original, staff_store_source(other), date(2026, 1, 1)
        )
        await repositories.staff.save(staff)
        await work.commit()
    path = f"/corporates/{fixture.corporate.id.value}/staffs/{staff.id.value}"
    headers = {"Authorization": "Bearer vendor"}
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        for store, hours, starts in [
            (fixture.store, "32", "2026-01-01"),
            (other, "8", "2026-01-01"),
            (fixture.store, "30.5", "2026-09-01"),
            (fixture.store, "31", "2026-09-01"),
        ]:
            response = await client.post(
                f"{path}/stores/{store.id.value}/work-conditions",
                headers=headers,
                json={
                    "weekly_hours": hours,
                    "effective_from": starts,
                    "duty": "pharmacist",
                },
            )
            assert response.status_code == 204, response.text
        old = await client.get(
            f"{path}/work-conditions",
            headers=headers,
            params={
                "store_id": str(fixture.store.id.value),
                "applied_on": "2026-08-31",
            },
        )
        current = await client.get(
            f"{path}/work-conditions",
            headers=headers,
            params={"applied_on": "2026-09-01"},
        )
        # Assert
        assert old.status_code == 200, old.text
        assert old.json()[0]["current"]["weekly_hours"] == "32"
        assert current.status_code == 200, current.text
        rows = {row["store_id"]: row for row in current.json()}
        assert rows[str(fixture.store.id.value)]["current"]["weekly_hours"] == "31"
        assert len(rows[str(fixture.store.id.value)]["history"]) == 3
        assert rows[str(other.id.value)]["current"]["weekly_hours"] == "8"


@pytest.mark.asyncio
async def test_勤務条件登録_未登録と明示的なゼロ_区別して保存する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    path = (
        f"/corporates/{fixture.corporate.id.value}/staffs/{fixture.staff[0].id.value}"
    )
    headers = {"Authorization": "Bearer vendor"}
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        for value in (None, "0"):
            response = await client.post(
                f"{path}/stores/{fixture.store.id.value}/work-conditions",
                headers=headers,
                json={
                    "weekly_hours": value,
                    "effective_from": "2026-01-01",
                    "duty": "other",
                },
            )
            assert response.status_code == 204, response.text
            result = await client.get(f"{path}/work-conditions", headers=headers)
            # Assert
            assert result.status_code == 200, result.text
            assert result.json()[0]["current"]["weekly_hours"] == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hours,expected_status", [("8", 200), ("8.01", 422), ("168.01", 422)]
)
async def test_店舗設定一括変更_二店舗目の勤務時間を検証_所属と権限も同じ保存単位で扱う(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    hours: str,
    expected_status: int,
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    other = create_store(corporate_id=fixture.corporate.id, name="一括変更先")
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).store.save(other)
        await work.commit()
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        original = await repositories.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[0].id
        )
        assert original is not None
        await repositories.staff.save(
            replace(original, weekly_contract_hours=WeeklyContractHours(Decimal("40")))
        )
        await work.commit()
    membership = fixture.memberships[0]
    base = f"/corporates/{fixture.corporate.id.value}"
    path = f"{base}/staffs/{fixture.staff[0].id.value}/work-conditions"
    headers = {"Authorization": "Bearer vendor"}
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        changed = await client.patch(
            f"{base}/users/{membership.id.value}",
            headers=headers,
            json={
                "store_roles": [
                    {"store_id": str(fixture.store.id.value), "role": "store_viewer"},
                    {"store_id": str(other.id.value), "role": "store_operator"},
                ],
                "store_work_conditions": [
                    {
                        "store_id": str(store.id.value),
                        "effective_from": "2026-11-03",
                        "starts_on": "2026-11-03"
                        if store == fixture.store
                        else "2026-11-01",
                        "weekly_hours": value,
                        "duty": "pharmacist",
                    }
                    for store, value in [(fixture.store, "32"), (other, hours)]
                ],
            },
        )
        # Assert
        assert changed.status_code == expected_status, changed.text
        result = await client.get(
            path, headers=headers, params={"applied_on": "2026-11-03"}
        )
        assert result.status_code == 200, result.text
        if expected_status == 200:
            by_store = {item["store_id"]: item for item in result.json()}
            assert (
                by_store[str(fixture.store.id.value)]["current"]["weekly_hours"] == "32"
            )
            assert by_store[str(other.id.value)]["current"]["weekly_hours"] == "8"
            # 同じ内容の再保存で履歴を増やさない。
            repeated = await client.patch(
                f"{base}/users/{membership.id.value}",
                headers=headers,
                json={
                    "store_work_conditions": [
                        {
                            "store_id": str(other.id.value),
                            "effective_from": "2026-11-03",
                            "weekly_hours": "8",
                            "duty": "pharmacist",
                        }
                    ]
                },
            )
            assert repeated.status_code == 200, repeated.text
            again = await client.get(path, headers=headers)
            assert (
                len(
                    next(
                        item
                        for item in again.json()
                        if item["store_id"] == str(other.id.value)
                    )["history"]
                )
                == 1
            )
        else:
            assert all(not item["history"] for item in result.json())
            assert str(other.id.value) not in {
                item["store_id"] for item in result.json()
            }
            user = await client.get(
                f"{base}/users/{membership.id.value}", headers=headers
            )
            assert str(other.id.value) not in user.json()["store_ids"]


@pytest.mark.asyncio
async def test_新規登録_選択した二店舗の権限と時間数_兼務所属と同時に再取得できる(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_organization(engine, session_factory)
    other = create_store(corporate_id=fixture.corporate.id, name="一括登録先")
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).store.save(other)
        await work.commit()
    base = f"/corporates/{fixture.corporate.id.value}"
    headers = {"Authorization": "Bearer vendor"}
    async with httpx.AsyncClient(
        transport=local_app(fixture), base_url="http://test"
    ) as client:
        # Act
        created = await client.post(
            f"{base}/staffs",
            headers=headers,
            json={
                "last_name": "薬局",
                "first_name": "花子",
                "last_name_kana": "ヤッキョク",
                "first_name_kana": "ハナコ",
                "pharmacist_license_number": "654321",
                "weekly_contract_hours": 40,
                "initial_home_store_id": str(fixture.store.id.value),
                "initial_start_date": "2026-11-03",
                "account": {
                    "login_id": "staff-multiple",
                    "password": "InitialPassword12345",
                    "store_roles": [
                        {
                            "store_id": str(fixture.store.id.value),
                            "role": "store_operator",
                        },
                        {"store_id": str(other.id.value), "role": "store_viewer"},
                    ],
                },
                "initial_store_work_conditions": [
                    {
                        "store_id": str(store.id.value),
                        "starts_on": "2026-11-03"
                        if store == fixture.store
                        else "2026-11-10",
                        "weekly_hours": hours,
                        "duty": "pharmacist",
                    }
                    for store, hours in [(fixture.store, "32"), (other, "8")]
                ],
            },
        )
        # Assert
        assert created.status_code == 201, created.text
        identifier = created.json()
        result = await client.get(
            f"{base}/staffs/{identifier['staff_id']}/work-conditions",
            headers=headers,
            params={"applied_on": "2026-11-10"},
        )
        assert result.status_code == 200, result.text
        rows = {item["store_id"]: item for item in result.json()}
        assert rows[str(fixture.store.id.value)]["is_primary"]
        assert not rows[str(other.id.value)]["is_primary"]
        assert rows[str(fixture.store.id.value)]["current"]["weekly_hours"] == "32"
        assert rows[str(other.id.value)]["current"]["weekly_hours"] == "8"
        membership = await client.get(
            f"{base}/users/{identifier['membership_id']}", headers=headers
        )
        assert {
            item["store_id"]: item["role"] for item in membership.json()["store_roles"]
        } == {
            str(fixture.store.id.value): "store_operator",
            str(other.id.value): "store_viewer",
        }

        assert rows[str(other.id.value)]["starts_on"] == "2026-11-10"
        before_other = await client.get(
            f"{base}/staffs/{identifier['staff_id']}/work-conditions",
            headers=headers,
            params={"applied_on": "2026-11-09"},
        )
        assert (
            next(
                item
                for item in before_other.json()
                if item["store_id"] == str(other.id.value)
            )["current"]
            is None
        )
