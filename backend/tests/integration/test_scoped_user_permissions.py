"""実DBの読取範囲とHTTP境界で、店舗単位の権限更新を確認する。"""

from dataclasses import replace
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.boundary_models import ActorRole
from app.application.access_control.policies import AuthorizationService
from app.application.identity.boundary_models import VerifiedSubject
from app.domain.identity.primitives import AccountStatus, MembershipRole
from app.domain.staff.value_objects import AffiliationPeriod, StoreAffiliation
from app.domain.store.exceptions import ManagerAssignmentConflictError
from app.domain.store.identifiers import StoreId
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.integration.organization_helpers import (
    Organization,
    external_subject_of,
    setup_organization,
)
from tests.integration.test_identity_http import identity_app


async def _setup(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession]
) -> tuple[Organization, StoreId]:
    fixture = await setup_organization(engine, factory)
    other = create_store(corporate_id=fixture.corporate.id, name="テスト他店舗")
    async with PostgresUnitOfWork(factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.store.save(other)
        manager_membership = await repositories.membership.get(
            fixture.memberships[0].id
        )
        target_membership = await repositories.membership.get(fixture.memberships[1].id)
        assert manager_membership is not None and target_membership is not None
        await repositories.membership.save(
            replace(
                manager_membership,
                role=MembershipRole.STORE_OPERATOR,
                store_ids=frozenset({fixture.store.id}),
            )
        )
        await repositories.membership.save(
            replace(
                target_membership,
                store_ids=frozenset({fixture.store.id, other.id}),
            )
        )
        target_staff = await repositories.staff.get(
            corporate_id=fixture.corporate.id, staff_id=fixture.staff[1].id
        )
        assert target_staff is not None
        await repositories.staff.save(
            replace(
                target_staff,
                affiliations=(
                    *target_staff.affiliations,
                    StoreAffiliation(
                        store_id=other.id,
                        is_primary=False,
                        period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                    ),
                ),
            )
        )
        await repositories.manager_assignment.save(
            create_manager_assignment(
                corporate_id=fixture.corporate.id,
                store_id=fixture.store.id,
                staff_id=fixture.staff[0].id,
                person_id=fixture.accounts[0].person_id,
            )
        )
        await work.commit()
    return fixture, other.id


@pytest.mark.asyncio
async def test_管理薬剤師_実DBで複数店舗利用の法人管理者を編集しても_他店舗と法人権限は維持する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    fixture, other = await _setup(engine, session_factory)
    actor = await fixture.root.resolve_identity(
        VerifiedSubject(principal_id=external_subject_of(0))
    )
    assert actor.managed_store_ids == frozenset({fixture.store.id})
    # Act
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=identity_app(fixture)),
        base_url="http://test",
        headers={"Authorization": "Bearer person"},
    ) as client:
        listing = await client.get(f"/corporates/{fixture.corporate.id.value}/users")
        assert listing.status_code == 200, listing.text
        changed = await client.patch(
            f"/corporates/{fixture.corporate.id.value}/users/{fixture.memberships[1].id.value}",
            json={"store_id": str(fixture.store.id.value), "store_is_active": False},
        )
        assert changed.status_code == 200, changed.text
        forbidden = await client.post(
            f"/accounts/{fixture.accounts[1].id.value}/suspension"
        )
        assert forbidden.status_code == 403, forbidden.text
    # Assert
    target = await fixture.root.resolve_identity(
        VerifiedSubject(principal_id=external_subject_of(1))
    )
    assert ActorRole.CORPORATE_ADMIN in target.roles
    assert target.store_ids == frozenset({other})
    patient = create_patient(corporate_id=fixture.corporate.id)
    stopped = create_prescription(
        corporate_id=fixture.corporate.id,
        store_id=fixture.store.id,
        patient_id=patient.id,
    )
    available = create_prescription(
        corporate_id=fixture.corporate.id, store_id=other, patient_id=patient.id
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        account = await repositories.user_account.get(fixture.accounts[1].id)
        assert account is not None and account.status == AccountStatus.ACTIVE
        await repositories.patient.save(patient)
        await repositories.prescription.save(stopped)
        await repositories.prescription.save(available)
        await work.commit()
    async with fixture.root.request_scope(
        authorization=AuthorizationService(replace(target, selected_store_id=other))
    ) as scope:
        rows = await scope.repositories.prescription.list_by_patient(
            corporate_id=fixture.corporate.id, patient_id=patient.id
        )
        assert [item.id for item in rows] == [available.id]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=identity_app(fixture, actor_index=1, selected_store_id=other)
        ),
        base_url="http://test",
        headers={"Authorization": "Bearer person"},
    ) as client:
        base = f"/corporates/{fixture.corporate.id.value}"
        hidden = await client.get(f"{base}/prescriptions/{stopped.id.value}")
        assert hidden.status_code == 404, hidden.text
        forbidden = await client.post(
            f"{base}/prescriptions/{stopped.id.value}/cancellation"
        )
        assert forbidden.status_code == 404, forbidden.text
        visible = await client.get(f"{base}/prescriptions/{available.id.value}")
        assert visible.status_code == 200, visible.text
        stores = await client.get(f"{base}/stores")
        assert stores.status_code == 200, stores.text
        assert {item["id"] for item in stores.json()} == {
            str(fixture.store.id.value),
            str(other.value),
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["membership", "staff"])
async def test_在任中の管理薬剤師_他店舗の権限や勤務を追加すると_保存前に拒否する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    change: str,
) -> None:
    # Arrange
    fixture, other = await _setup(engine, session_factory)
    # Act / Assert
    with pytest.raises(ManagerAssignmentConflictError):
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            if change == "membership":
                await scope.use_cases.identity.change_membership.execute(
                    str(fixture.corporate.id.value),
                    str(fixture.memberships[0].id.value),
                    store_ids=(str(fixture.store.id.value), str(other.value)),
                )
            else:
                await scope.repositories.staff.save(
                    replace(
                        fixture.staff[0],
                        affiliations=fixture.staff[0].affiliations
                        + (
                            StoreAffiliation(
                                store_id=other,
                                is_primary=False,
                                period=AffiliationPeriod(start_date=date(2026, 9, 17)),
                            ),
                        ),
                    )
                )
    actor = await fixture.root.resolve_identity(
        VerifiedSubject(principal_id=external_subject_of(0))
    )
    assert actor.store_ids == frozenset({fixture.store.id})


@pytest.mark.asyncio
async def test_法人管理者_自法人のアカウントを停止すると_既存の資格情報でも次の要求は拒否する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    fixture, _ = await _setup(engine, session_factory)
    actor = await fixture.root.resolve_identity(
        VerifiedSubject(principal_id=external_subject_of(1))
    )
    # Act
    async with fixture.root.request_scope(
        authorization=AuthorizationService(actor)
    ) as scope:
        await scope.use_cases.identity.suspend_account.execute(
            str(fixture.accounts[0].id.value)
        )
    # Assert
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=identity_app(fixture)),
        base_url="http://test",
        headers={"Authorization": "Bearer person"},
    ) as client:
        response = await client.get("/me")
    assert response.status_code == 401, response.text
