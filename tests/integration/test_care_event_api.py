"""CareEventのHTTP作成・取得契約を実PostgreSQLで検証する。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryRecordId,
    TracingReportId,
)
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.primitives import StoreId
from app.domain.store.store import Store
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    create_record,
    create_tracing_report,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.stub_actor_context_provider import VALID_TOKEN
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    _count,
    setup_clinical,
)
from tests.integration.test_cross_store_follow_up import (
    _app_for_actor,
    _save_corporate_admin,
    _save_store_operator,
)
from tests.integration.test_identity_persistence import _person


async def _save_store_viewer(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
) -> FastAPI:
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey(
            f"issuer/integration-care-event-viewer-{uuid4()}"
        ),
    )
    staff = replace(
        create_staff(
            corporate_id=corporate_id, code=f"VIEWER{uuid4().hex[:6].upper()}"
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store_id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(
        id=staff.id,
        corporate_id=corporate_id,
        person_id=person.id,
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate_id,
        role=MembershipRole.STORE_VIEWER,
        store_ids=frozenset({store_id}),
        staff_id=staff.id,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.membership.save(membership)
        await work.commit()

    assert account.external_subject is not None
    actor = ResolvedActorContext(
        principal_id=account.external_subject.value,
        roles=frozenset({ActorRole.STORE_VIEWER}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate_id,
        staff_id=staff.id,
        store_ids=membership.store_ids,
    )
    return _app_for_actor(engine, session_factory, actor)


async def _save_unique_corporate_admin(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    corporate_id: CorporateId,
) -> FastAPI:
    """他のテストActorと衝突しない法人管理者を保存する。"""
    person = _person()
    subject = ExternalSubjectKey(f"issuer/care-event-admin-{uuid4()}")
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=subject,
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate_id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset(),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.account_person.save(person)
        await repositories.user_account.save(account)
        await repositories.membership.save(membership)
        await work.commit()
    actor = ResolvedActorContext(
        principal_id=subject.value,
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate_id,
    )
    return _app_for_actor(engine, session_factory, actor)


async def _save_secondary_store(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    corporate_id: CorporateId,
) -> Store:
    store = create_store(corporate_id=corporate_id, name="別店舗")
    person = _person()
    staff = replace(
        create_staff(corporate_id=corporate_id, code=f"MGR{uuid4().hex[:6].upper()}"),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("987654"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(
        id=staff.id,
        corporate_id=corporate_id,
        person_id=person.id,
    )
    assignment = create_manager_assignment(
        corporate_id=corporate_id,
        store_id=store.id,
        staff_id=staff.id,
        person_id=person.id,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.store.save(store)
        await repos.account_person.save(person)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.manager_assignment.save(assignment)
        await work.commit()
    return store


@pytest.mark.asyncio
async def test_tc45_11_12_60_Event作成取得と入力拒否がHTTPから成立する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """新規Eventを保存して取得し、発生日時省略と監査値指定を拒否する。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    operator = await _save_store_operator(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    async with PostgresUnitOfWork(session_factory) as work:
        definitions = await PostgresRepositorySet.create(
            work
        ).event_definition.list_for_corporate(corporate_id=clinical.corporate_id)
    definition = next(
        item
        for item in definitions
        if item.corporate_id is None
        and item.standard_code is not None
        and item.standard_code.value == "in_person_consultation"
    )
    baseline = await _count(engine, "care_events")
    event_url = f"/corporates/{clinical.corporate_id.value}/events"
    body = {
        "store_id": str(operator.store.id.value),
        "patient_id": str(clinical.record.patient_id.value),
        "event_type_id": str(definition.id.value),
        "occurred_at": datetime(2026, 9, 20, 4, tzinfo=UTC).isoformat(),
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        created = await client.post(event_url, json=body)
        missing_time = await client.post(
            event_url,
            json={key: value for key, value in body.items() if key != "occurred_at"},
        )
        forged_audit = await client.post(
            event_url,
            json={**body, "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
        )
        retrieved = await client.get(
            f"/corporates/{clinical.corporate_id.value}/events/"
            f"{created.json().get('event_id', '')}"
        )

    assert created.status_code == 201, created.text
    assert created.json()["medication_history_id"] is None
    assert created.json()["occurred_at_is_unknown"] is False
    assert created.json()["prescription_id"] is None
    assert created.json()["dispensing_id"] is None
    assert retrieved.status_code == 200, retrieved.text
    assert retrieved.json()["event_id"] == created.json()["event_id"]
    assert retrieved.json()["created_at"] != body["occurred_at"]
    assert missing_time.status_code == 422
    assert forged_audit.status_code == 422
    assert await _count(engine, "care_events") == baseline + 1


@pytest.mark.asyncio
async def test_tc45_care_event_http認可マトリクス(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """法人管理者・店舗オペレータ・店舗ビューア・未認証の認可境界をHTTP経由で検証する。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    corp_id = clinical.corporate_id
    operator_fixture = await _save_store_operator(
        engine, session_factory, corporate_id=corp_id
    )
    store1 = operator_fixture.store
    store2 = await _save_secondary_store(session_factory, corporate_id=corp_id)
    admin_app = await _save_corporate_admin(
        engine, session_factory, corporate_id=corp_id
    )
    operator_app = operator_fixture.app
    viewer_app = await _save_store_viewer(
        engine, session_factory, corporate_id=corp_id, store_id=store1.id
    )
    foreign_corporate = create_corporate("Event認可別法人")
    foreign_patient = create_patient(corporate_id=foreign_corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(foreign_corporate)
        await repositories.patient.save(foreign_patient)
        await work.commit()
    foreign_admin_app = await _save_unique_corporate_admin(
        engine, session_factory, corporate_id=foreign_corporate.id
    )
    foreign_store = await _save_secondary_store(
        session_factory, corporate_id=foreign_corporate.id
    )
    viewer_store2_app = await _save_store_viewer(
        engine, session_factory, corporate_id=corp_id, store_id=store2.id
    )

    # 1. 法人管理者:
    # 独自種別の作成 (201) と更新 (200) が成立
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=admin_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        def_res = await client.post(
            f"/corporates/{corp_id.value}/event-definitions",
            json={"name": "管理者独自種別"},
        )
        assert def_res.status_code == 201, def_res.text
        def_id = def_res.json()["id"]

        patch_res = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"name": "管理者独自種別(改)", "is_active": True},
        )
        assert patch_res.status_code == 200, patch_res.text
        assert patch_res.json()["name"] == "管理者独自種別(改)"

        # 管理者はstore2でのEvent作成も可能
        event_store2_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store2.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        assert event_store2_res.status_code == 201, event_store2_res.text
        store2_event_id = event_store2_res.json()["event_id"]

    # 店舗状態が休止へ変わった後も、許可店舗の既存Eventは読める。
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_store2 = await repositories.store.get(store2.id)
        assert stored_store2 is not None
        await repositories.store.save(
            replace(stored_store2, status=StoreStatus.SUSPENDED)
        )
        await work.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=foreign_admin_app, raise_app_exceptions=False
        ),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        foreign_def_res = await client.post(
            f"/corporates/{foreign_corporate.id.value}/event-definitions",
            json={"name": "別法人独自種別"},
        )
        assert foreign_def_res.status_code == 201, foreign_def_res.text
        foreign_def_id = foreign_def_res.json()["id"]
    foreign_event_res = await _create_event_as_foreign_admin(
        foreign_admin_app,
        corporate_id=foreign_corporate.id,
        store_id=foreign_store.id,
        patient_id=foreign_patient.id,
        event_type_id=foreign_def_id,
    )
    assert foreign_event_res.status_code == 201, foreign_event_res.text
    foreign_event_id = foreign_event_res.json()["event_id"]

    # 2. 店舗オペレータ (store1管轄):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        definitions_res = await client.get(
            f"/corporates/{corp_id.value}/event-definitions"
        )
        assert definitions_res.status_code == 200, definitions_res.text
        assert def_id in {item["id"] for item in definitions_res.json()}

        # 種別作成は 403
        op_def_res = await client.post(
            f"/corporates/{corp_id.value}/event-definitions",
            json={"name": "オペレータ種別"},
        )
        assert op_def_res.status_code == 403, op_def_res.text
        op_def_update = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"name": "店舗担当の改名"},
        )
        op_def_deactivate = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"is_active": False},
        )
        assert op_def_update.status_code == 403, op_def_update.text
        assert op_def_deactivate.status_code == 403, op_def_deactivate.text

        # 管轄店舗store1でのEvent作成は 201
        op_ev_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        assert op_ev_res.status_code == 201, op_ev_res.text
        store1_event_id = op_ev_res.json()["event_id"]

        history_baseline = await _count(engine, "medication_history_records")
        first_history = await client.post(
            f"/corporates/{corp_id.value}/events/{store1_event_id}/medication-history",
            json={},
        )
        duplicate_history = await client.post(
            f"/corporates/{corp_id.value}/events/{store1_event_id}/medication-history",
            json={},
        )
        assert first_history.status_code == 201, first_history.text
        assert duplicate_history.status_code == 409, duplicate_history.text
        assert (
            await _count(engine, "medication_history_records") == history_baseline + 1
        )

        # 管轄店舗store1のEvent参照は 200
        get_store1_res = await client.get(
            f"/corporates/{corp_id.value}/events/{store1_event_id}"
        )
        assert get_store1_res.status_code == 200, get_store1_res.text

        # 管轄外店舗store2でのEvent作成は 404 (店舗未検出として隠蔽)
        op_ev_store2_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store2.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        assert op_ev_store2_res.status_code == 404, op_ev_store2_res.text

        # 管轄外店舗store2のEvent参照は 404 (ReadScopeによる隠蔽)
        get_store2_res = await client.get(
            f"/corporates/{corp_id.value}/events/{store2_event_id}"
        )
        assert get_store2_res.status_code == 404, get_store2_res.text

        # 他法人の患者・Event種別・Event IDは同じ法人の操作から隠す。
        event_count_before_denials = await _count(engine, "care_events")
        foreign_patient_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(foreign_patient.id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        foreign_definition_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": foreign_def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        foreign_event_res = await client.get(
            f"/corporates/{corp_id.value}/events/{foreign_event_id}"
        )
        other_corporate_route_res = await client.get(
            f"/corporates/{foreign_corporate.id.value}/events/{foreign_event_id}"
        )
        malformed_time_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": "not-a-time",
            },
        )
        assert foreign_patient_res.status_code == 404, foreign_patient_res.text
        assert foreign_definition_res.status_code == 404, foreign_definition_res.text
        assert foreign_event_res.status_code == 404, foreign_event_res.text
        assert other_corporate_route_res.status_code == 404, (
            other_corporate_route_res.text
        )
        assert malformed_time_res.status_code == 422, malformed_time_res.text
        assert await _count(engine, "care_events") == event_count_before_denials

    # 3. 店舗ビューア (store1管轄):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=viewer_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        viewer_definitions_res = await client.get(
            f"/corporates/{corp_id.value}/event-definitions"
        )
        assert viewer_definitions_res.status_code == 200, viewer_definitions_res.text

        # 種別作成は 403
        vw_def_res = await client.post(
            f"/corporates/{corp_id.value}/event-definitions",
            json={"name": "ビューア種別"},
        )
        assert vw_def_res.status_code == 403, vw_def_res.text
        vw_def_update = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"name": "閲覧者の改名"},
        )
        vw_def_deactivate = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"is_active": False},
        )
        assert vw_def_update.status_code == 403, vw_def_update.text
        assert vw_def_deactivate.status_code == 403, vw_def_deactivate.text

        # Event作成は権限なしで 403
        vw_ev_res = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        assert vw_ev_res.status_code == 403, vw_ev_res.text

        # 管轄店舗store1のEvent参照は 200
        vw_get_store1_res = await client.get(
            f"/corporates/{corp_id.value}/events/{store1_event_id}"
        )
        assert vw_get_store1_res.status_code == 200, vw_get_store1_res.text

        # 管轄外店舗store2のEvent参照は 404
        vw_get_store2_res = await client.get(
            f"/corporates/{corp_id.value}/events/{store2_event_id}"
        )
        assert vw_get_store2_res.status_code == 404, vw_get_store2_res.text

    # 3b. 休止店舗のEvent参照も、店舗閲覧者の読取範囲内なら許可する。
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=viewer_store2_app, raise_app_exceptions=False
        ),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        suspended_store_read = await client.get(
            f"/corporates/{corp_id.value}/events/{store2_event_id}"
        )
        assert suspended_store_read.status_code == 200, suspended_store_read.text

    # 他法人管理者による自法人定義の更新は対象不存在として隠す。
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(
            app=foreign_admin_app, raise_app_exceptions=False
        ),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        foreign_admin_update = await client.patch(
            f"/corporates/{corp_id.value}/event-definitions/{def_id}",
            json={"name": "越境改名"},
        )
        assert foreign_admin_update.status_code == 404, foreign_admin_update.text

    # 4. 未認証クライアント:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        unauth_get = await client.get(
            f"/corporates/{corp_id.value}/events/{store1_event_id}"
        )
        assert unauth_get.status_code == 401, unauth_get.text

        unauth_post = await client.post(
            f"/corporates/{corp_id.value}/events",
            json={
                "store_id": str(store1.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": def_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
        assert unauth_post.status_code == 401, unauth_post.text


@pytest.mark.asyncio
async def test_tc45_全Event種別で共通薬歴を更新確定できる(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """6標準種別と法人独自種別で同じ下書き・レビュー・確定経路を通す。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    operator = await _save_store_operator(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    admin_app = await _save_corporate_admin(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    corporate_path = f"/corporates/{clinical.corporate_id.value}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=admin_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        custom_definition = await client.post(
            f"{corporate_path}/event-definitions", json={"name": "個別訪問"}
        )
    assert custom_definition.status_code == 201, custom_definition.text

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        listed_definitions = await client.get(f"{corporate_path}/event-definitions")
        assert listed_definitions.status_code == 200, listed_definitions.text
        definitions = listed_definitions.json()
        assert len(definitions) == 7
        assert custom_definition.json()["id"] in {item["id"] for item in definitions}
        baseline_events = await _count(engine, "care_events")
        baseline_histories = await _count(engine, "medication_history_records")
        consultation_record_id: str | None = None
        expected_allergens: dict[str, str] = {}

        for index, definition in enumerate(definitions):
            event_response = await client.post(
                f"{corporate_path}/events",
                json={
                    "store_id": str(operator.store.id.value),
                    "patient_id": str(clinical.record.patient_id.value),
                    "event_type_id": definition["id"],
                    "occurred_at": datetime(2026, 9, 19, 3, tzinfo=UTC).isoformat(),
                },
            )
            assert event_response.status_code == 201, event_response.text
            event_id = event_response.json()["event_id"]
            started = await client.post(
                f"{corporate_path}/events/{event_id}/medication-history", json={}
            )
            assert started.status_code == 201, started.text
            record_id = started.json()["id"]
            if definition.get("standard_code") == "in_person_consultation":
                consultation_record_id = record_id

            record_path = f"{corporate_path}/medication-histories/{record_id}"
            blank_finalize = await client.post(
                f"{record_path}/finalization",
                json={"review_result": "assessment_and_instruction_recorded"},
            )
            assert blank_finalize.status_code == 422, blank_finalize.text

            partial = await client.put(
                f"{record_path}/draft",
                json={"soap": {"subjective": [{"text": f"主観{index}"}]}},
            )
            assert partial.status_code == 200, partial.text
            missing_checklist = await client.post(
                f"{record_path}/finalization",
                json={"review_result": "assessment_and_instruction_recorded"},
            )
            assert missing_checklist.status_code == 422, missing_checklist.text

            allergen = f"横断アレルゲン{index}"
            expected_allergens[record_id] = allergen
            updated = await client.put(
                f"{record_path}/draft",
                json={
                    "soap": {
                        "subjective": [{"text": f"主観{index}"}],
                        "objective": [{"text": f"客観{index}"}],
                        "assessment": [{"text": f"評価{index}"}],
                        "plan": [{"text": f"計画{index}"}],
                    },
                    "method": "face_to_face",
                    "handbook_status": {"presented": True},
                    "residual_drug": {"has_residual_drugs": False},
                    "information_sheet_provided": True,
                    "profile_updates": {
                        "new_allergies": [
                            {
                                "allergen": allergen,
                                "reaction": "発疹",
                                "severity": "mild",
                            }
                        ]
                    },
                },
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["event_id"] == event_id
            assert updated.json()["prescription_id"] is None
            assert updated.json()["dispensing_id"] is None
            assert updated.json()["billing_additions"] == []
            assert updated.json()["soap"]["assessment"][0]["text"] == f"評価{index}"
            assert updated.json()["updates_profile"] is True

            missing_review = await client.post(f"{record_path}/finalization", json={})
            assert missing_review.status_code == 422, missing_review.text
            finalized = await client.post(
                f"{record_path}/finalization",
                json={"review_result": "assessment_and_instruction_recorded"},
            )
            assert finalized.status_code == 200, finalized.text
            assert finalized.json()["status"] == "finalized"
            assert finalized.json()["finalized_by"] == str(operator.staff_id.value)
            assert (
                finalized.json()["finalized_at"]
                == datetime(2026, 9, 20, 3, tzinfo=UTC).isoformat()
            )

            retrieved = await client.get(record_path)
            assert retrieved.status_code == 200, retrieved.text
            assert retrieved.json()["event_id"] == event_id
            event_read = await client.get(f"{corporate_path}/events/{event_id}")
            assert event_read.status_code == 200, event_read.text
            assert event_read.json()["medication_history_id"] == record_id

            if definition.get("standard_code") == "in_person_consultation":
                statutory = await client.get(
                    f"{record_path}/statutory-record-sufficiency"
                )
                assert statutory.status_code == 422, statutory.text

        assert consultation_record_id is not None
        assert await _count(engine, "care_events") == baseline_events + 7
        assert (
            await _count(engine, "medication_history_records") == baseline_histories + 7
        )
        async with PostgresUnitOfWork(session_factory) as work:
            profile = await PostgresRepositorySet.create(
                work
            ).patient_medical_profile.get_by_patient(
                corporate_id=clinical.corporate_id,
                patient_id=clinical.record.patient_id,
            )
        assert profile is not None
        for record_id, allergen in expected_allergens.items():
            allergy = next(
                item for item in profile.allergies if item.allergen.value == allergen
            )
            assert str(allergy.provenance.source_record_id.value) == record_id

        # 法定調剤録の照合対象は、処方箋受付Eventにある関連ID付き薬歴に限る。
        async with _client(clinical) as clinical_client:
            prescription_statutory = await clinical_client.get(
                f"{corporate_path}/medication-histories/{clinical.record.id.value}"
                "/statutory-record-sufficiency"
            )
        assert prescription_statutory.status_code == 200, prescription_statutory.text
        assert prescription_statutory.json()["dispensing_id"] == str(
            clinical.process.id.value
        )

        # Event種別に依存せず、確定した薬歴へレポートと返答を記録できる。
        report_response = await client.post(
            f"{corporate_path}/medication-histories/{consultation_record_id}"
            "/tracing-reports",
            json={
                "reporter_id": str(operator.staff_id.value),
                "provided_at": datetime(2026, 9, 20, 3, 15, tzinfo=UTC).isoformat(),
                "medical_institution_name": "地域医療センター",
                "physician_name": "佐藤医師",
                "category": "residual_drug",
                "fee_category": "fee_1",
                "delivery_method": "fax",
                "content": "残薬状況を確認した。",
            },
        )
        assert report_response.status_code == 201, report_response.text
        report_id = report_response.json()["tracing_reports"][0]["id"]
        response_record = await client.post(
            f"{corporate_path}/medication-histories/{consultation_record_id}"
            f"/tracing-reports/{report_id}/response",
            json={
                "responded_at": datetime(2026, 9, 20, 3, 30, tzinfo=UTC).isoformat(),
                "content": "次回処方で調整します。",
                "action_type": "agreed_reflect_next",
                "received_by": str(operator.staff_id.value),
            },
        )
        assert response_record.status_code == 200, response_record.text
        assert (
            response_record.json()["tracing_reports"][0]["response"]["content"]
            == "次回処方で調整します。"
        )


@pytest.mark.asyncio
async def test_tc45_44_遡及Event薬歴確定後の頭書きは全件再構築と一致する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """後日の確定記録がある患者へ過去日時のEvent薬歴を確定する。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    async with _client(clinical) as client:
        initial_finalization = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{clinical.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )
    assert initial_finalization.status_code == 200, initial_finalization.text

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        profile_before = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=clinical.record.patient_id,
        )
    assert profile_before is not None

    operator = await _save_store_operator(
        engine,
        session_factory,
        corporate_id=clinical.corporate_id,
    )
    corporate_path = f"/corporates/{clinical.corporate_id.value}"
    backdated_counseling = datetime(2026, 9, 19, 2, tzinfo=UTC)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        definitions = await client.get(f"{corporate_path}/event-definitions")
        assert definitions.status_code == 200, definitions.text
        consultation = next(
            item
            for item in definitions.json()
            if item["standard_code"] == "in_person_consultation"
        )
        event_response = await client.post(
            f"{corporate_path}/events",
            json={
                "store_id": str(operator.store.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": consultation["id"],
                "occurred_at": backdated_counseling.isoformat(),
            },
        )
        assert event_response.status_code == 201, event_response.text
        event_id = event_response.json()["event_id"]
        started = await client.post(
            f"{corporate_path}/events/{event_id}/medication-history", json={}
        )
        assert started.status_code == 201, started.text
        record_id = started.json()["id"]
        record_path = f"{corporate_path}/medication-histories/{record_id}"
        updated = await client.put(
            f"{record_path}/draft",
            json={
                "soap": {
                    "subjective": [{"text": "以前からの症状を確認した。"}],
                    "objective": [{"text": "状態に変化はない。"}],
                    "assessment": [{"text": "継続可能と判断した。"}],
                    "plan": [{"text": "次回も経過を確認する。"}],
                },
                "method": "face_to_face",
                "handbook_status": {"presented": True},
                "residual_drug": {"has_residual_drugs": False},
                "information_sheet_provided": True,
                "profile_updates": {
                    "new_allergies": [
                        {
                            "allergen": "遡及記録アレルゲン",
                            "reaction": "発疹",
                            "severity": "mild",
                        }
                    ]
                },
            },
        )
        assert updated.status_code == 200, updated.text
        finalized = await client.post(
            f"{record_path}/finalization",
            json={
                "counseled_at": backdated_counseling.isoformat(),
                "delay_reason": "過去の相談記録を確認して追記したため",
                "review_result": "assessment_and_instruction_recorded",
            },
        )
        assert finalized.status_code == 200, finalized.text
        assert finalized.json()["counseled_at"] == backdated_counseling.isoformat()

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        projected = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=clinical.record.patient_id,
        )
        records = await repositories.medication_history.list_for_profile_projection(
            corporate_id=clinical.corporate_id,
            patient_id=clinical.record.patient_id,
        )
    assert projected is not None
    rebuilt = PatientMedicalProfile.rebuild_from(
        corporate_id=clinical.corporate_id,
        patient_id=clinical.record.patient_id,
        records=tuple(records),
    )
    assert projected.id == profile_before.id
    assert projected.allergies == rebuilt.allergies
    assert projected.adverse_reactions == rebuilt.adverse_reactions
    assert projected.medical_conditions == rebuilt.medical_conditions
    assert projected.concurrent_medications == rebuilt.concurrent_medications
    assert projected.lifestyle == rebuilt.lifestyle
    assert projected.generic_preference == rebuilt.generic_preference
    assert projected.family_pharmacist == rebuilt.family_pharmacist
    assert projected.source_record_ids == rebuilt.source_record_ids
    assert str(finalized.json()["id"]) in projected.source_record_ids


@pytest.mark.asyncio
async def test_tc45_22_Eventへの同時薬歴作成は一件だけ成功する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同じEventに同時起票しても一意制約により薬歴を1件だけ保存する。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    operator = await _save_store_operator(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    corporate_path = f"/corporates/{clinical.corporate_id.value}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        definitions = await client.get(f"{corporate_path}/event-definitions")
        assert definitions.status_code == 200, definitions.text
        definition = next(
            item
            for item in definitions.json()
            if item["standard_code"] == "in_person_consultation"
        )
        event = await client.post(
            f"{corporate_path}/events",
            json={
                "store_id": str(operator.store.id.value),
                "patient_id": str(clinical.record.patient_id.value),
                "event_type_id": definition["id"],
                "occurred_at": datetime(2026, 9, 19, 3, tzinfo=UTC).isoformat(),
            },
        )
    assert event.status_code == 201, event.text
    event_id = event.json()["event_id"]
    baseline = await _count(engine, "medication_history_records")

    async def create_history() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        ) as client:
            return await client.post(
                f"{corporate_path}/events/{event_id}/medication-history", json={}
            )

    responses = await asyncio.gather(create_history(), create_history())
    assert sorted(response.status_code for response in responses) == [201, 409], [
        (response.status_code, response.text) for response in responses
    ]
    assert await _count(engine, "medication_history_records") == baseline + 1


@pytest.mark.asyncio
async def test_tc45_54_旧親IDとレポートIDで移行先の返答を追記する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """旧親IDとレポートIDのAPI要求を、対応表の移行先薬歴へ記録する。"""
    clinical: ClinicalFixture = await setup_clinical(engine, session_factory)
    operator = await _save_store_operator(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    counseled_at = datetime(2026, 9, 19, 3, tzinfo=UTC)
    finalized_at = datetime(2026, 9, 19, 4, tzinfo=UTC)

    def new_record() -> MedicationHistoryRecord:
        draft = create_record(
            corporate_id=clinical.corporate_id,
            store_id=operator.store.id,
            patient_id=clinical.record.patient_id,
            counselor_id=operator.staff_id,
            counseled_at=counseled_at,
        )
        return finalize_record_with_review(
            replace(draft, prescription_id=None, dispensing_id=None),
            finalized_by=operator.staff_id,
            finalized_at=FinalizedTimestamp(finalized_at),
        )

    parent = new_record()
    target = new_record()
    report_id = TracingReportId.generate()
    target = target.add_tracing_report(
        create_tracing_report(
            report_id=report_id,
            reporter_id=operator.staff_id,
            provided_at=datetime(2026, 9, 20, 3, 10, tzinfo=UTC),
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await save_history_with_event(repositories, parent)
        await repositories.medication_history.save(parent)
        await save_history_with_event(repositories, target)
        await repositories.medication_history.save(target)
        await work.session.execute(
            insert(schema.legacy_tracing_report_links).values(
                corporate_id=clinical.corporate_id.value,
                legacy_parent_record_id=parent.id.value,
                legacy_tracing_report_id=report_id.value,
                target_record_id=target.id.value,
                created_at=finalized_at,
            )
        )
        await work.commit()

    corporate_path = f"/corporates/{clinical.corporate_id.value}"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        response = await client.post(
            f"{corporate_path}/medication-histories/{parent.id.value}"
            f"/tracing-reports/{report_id.value}/response",
            json={
                "responded_at": datetime(2026, 9, 20, 3, 30, tzinfo=UTC).isoformat(),
                "content": "次回処方時に調整します。",
                "action_type": "agreed_reflect_next",
                "received_by": str(operator.staff_id.value),
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(target.id.value)
    assert response.json()["tracing_reports"][0]["id"] == str(report_id.value)
    assert response.json()["tracing_reports"][0]["response"]["content"] == (
        "次回処方時に調整します。"
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_parent = await repositories.medication_history.get(
            corporate_id=clinical.corporate_id,
            record_id=MedicationHistoryRecordId(parent.id.value),
        )
        stored_target = await repositories.medication_history.get(
            corporate_id=clinical.corporate_id,
            record_id=MedicationHistoryRecordId(target.id.value),
        )
    assert stored_parent is not None and stored_parent.tracing_reports == ()
    assert stored_target is not None
    assert stored_target.tracing_reports[0].response is not None


async def _create_event_as_foreign_admin(
    admin_app: FastAPI,
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    patient_id: PatientId,
    event_type_id: str,
) -> httpx.Response:
    """別法人のEventを作り、他法人ID秘匿テストの有効な参照先にする。"""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=admin_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        return await client.post(
            f"/corporates/{corporate_id.value}/events",
            json={
                "store_id": str(store_id.value),
                "patient_id": str(patient_id.value),
                "event_type_id": event_type_id,
                "occurred_at": datetime(2026, 9, 20, 5, tzinfo=UTC).isoformat(),
            },
        )
