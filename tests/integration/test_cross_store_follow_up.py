"""店舗を横断する独立フォローアップの実DB境界を検証する。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.account_person import AccountPerson
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
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.store import Store
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.presentational.app_factory import create_app
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_independent_follow_up_record,
    create_record,
    finalize_record_with_review,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    _count,
    _version,
    reject_profile_writes,
    setup_clinical,
)
from tests.integration.test_identity_persistence import _person

_CLOCK = FakeClock(datetime(2026, 9, 20, 3, tzinfo=UTC))
_FOLLOWED_UP_AT = datetime(2026, 9, 21, 3, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class StoreOperatorFixture:
    """B店の店舗オペレータと認証済み薬剤師。"""

    store: Store
    person: AccountPerson
    account: UserAccount
    staff_id: StaffId
    membership: CorporateMembership
    app: FastAPI


async def _save_store_operator(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    corporate_id: CorporateId,
    clock: FakeClock = _CLOCK,
) -> StoreOperatorFixture:
    """B店、薬剤師、店舗範囲を持つアカウント、管理薬剤師任命を保存する。"""
    store = create_store(corporate_id=corporate_id, name="フォローアップB店")
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey("issuer/integration-follow-up-b"),
    )
    staff = replace(
        create_staff(corporate_id=corporate_id, code="FOLLOWUPB"),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("654321"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate_id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({store.id}),
        staff_id=staff.id,
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
        repositories = PostgresRepositorySet.create(work)
        await repositories.store.save(store)
        await repositories.account_person.save(person)
        await repositories.user_account.save(account)
        await repositories.staff.save(staff)
        await repositories.staff_person_link.save(link)
        await repositories.membership.save(membership)
        await repositories.manager_assignment.save(assignment)
        await work.commit()

    actor = ResolvedActorContext(
        principal_id="issuer/integration-follow-up-b",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate_id,
        staff_id=staff.id,
        store_ids=membership.store_ids,
    )
    app = _app_for_actor(engine, session_factory, actor, clock=clock)
    return StoreOperatorFixture(
        store=store,
        person=person,
        account=account,
        staff_id=staff.id,
        membership=membership,
        app=app,
    )


async def _save_corporate_admin(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    corporate_id: CorporateId,
) -> FastAPI:
    """法人全体を担当する法人管理者を保存してアプリを組み立てる。"""
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey("issuer/integration-follow-up-admin"),
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
        principal_id="issuer/integration-follow-up-admin",
        roles=frozenset({ActorRole.CORPORATE_ADMIN}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate_id,
    )
    return _app_for_actor(engine, session_factory, actor)


def _app_for_actor(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    actor: ResolvedActorContext,
    *,
    clock: FakeClock = _CLOCK,
) -> FastAPI:
    """本番のComposition Rootへ指定Actorだけを接続する。"""
    provider = StubActorContextProvider(actor)
    app = create_app(actor_provider=provider)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=provider,
            composition_root=PostgresCompositionRoot(engine, session_factory, clock),
        ),
    )
    return app


def _follow_up_body(operator: StoreOperatorFixture) -> dict[str, Any]:
    """B店の薬剤師による独立薬歴入力を作る。"""
    return {
        "store_id": str(operator.store.id.value),
        "patient_id": "",  # 呼び出し側で参照元患者を設定する。
        "counselor_id": str(operator.staff_id.value),
        "followed_up_at": _FOLLOWED_UP_AT.isoformat(),
        "method": "telephone",
        "soap": {
            "subjective": [{"text": "服用後の変化を確認した。"}],
            "objective": [{"text": "症状の悪化は認めない。"}],
            "assessment": [{"text": "継続可能と判断した。"}],
            "plan": [{"text": "次回も状態を確認する。"}],
        },
        "profile_updates": {
            "new_allergies": [
                {
                    "allergen": "そば",
                    "reaction": "蕁麻疹",
                    "severity": "moderate",
                }
            ]
        },
    }


async def _finalize_initial(
    fixture: ClinicalFixture,
    session_factory: async_sessionmaker[AsyncSession],
) -> MedicationHistoryRecord:
    """A店の初回薬歴をHTTPで確定し、保存済み集約を返す。"""
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/medication-histories/{fixture.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )
    assert response.status_code == 200, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        record = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id,
            record_id=fixture.record.id,
        )
    assert record is not None
    return record


@pytest.mark.asyncio
async def test_tc31_フォローアップ確定と頭書き投影が同じDBトランザクションで戻る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """頭書きだけを失敗させ、B店薬歴の確定と監査も巻き戻ることを確かめる。"""
    clinical = await setup_clinical(engine, session_factory)
    source = await _finalize_initial(clinical, session_factory)
    operator = await _save_store_operator(
        engine,
        session_factory,
        corporate_id=clinical.corporate_id,
        clock=FakeClock(datetime(2026, 9, 22, 3, tzinfo=UTC)),
    )
    body = _follow_up_body(operator)
    body["patient_id"] = str(source.patient_id.value)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        created = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{source.id.value}/follow-ups",
            json=body,
        )
    assert created.status_code == 201, created.text
    follow_up_id = created.json()["id"]
    baseline_audits = await _count(engine, "operation_audits")
    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=source.patient_id,
        )
    assert profile is not None
    baseline_version = await _version(
        engine, "medication_history_records", follow_up_id
    )

    async with (
        reject_profile_writes(engine),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        ) as client,
    ):
        failed = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{follow_up_id}/finalization",
            json={
                "review_result": "assessment_and_instruction_recorded",
                "delay_reason": "患者への後日確認のため翌日確定",
            },
        )

    assert failed.status_code == 500, failed.text
    assert (
        await _version(engine, "medication_history_records", follow_up_id)
        == baseline_version
    )
    assert await _count(engine, "operation_audits") == baseline_audits
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        follow_up = await repositories.medication_history.get(
            corporate_id=clinical.corporate_id,
            record_id=MedicationHistoryRecordId.parse(follow_up_id),
        )
        current_profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=source.patient_id,
        )
    assert follow_up is not None and follow_up.status is MedicationHistoryStatus.DRAFT
    assert current_profile is not None
    assert current_profile.id == profile.id
    assert current_profile.allergies == profile.allergies
    assert await _version(engine, "patient_medical_profiles", profile.id.value) == 1


@pytest.mark.asyncio
async def test_tc38_tc46_B店Actorは独立薬歴だけを読み_他店下書きは推測できない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """候補は横断参照でき、本文読取と一覧はB店の範囲に限られる。"""
    clinical = await setup_clinical(engine, session_factory)
    source = await _finalize_initial(clinical, session_factory)
    source_version = await _version(
        engine, "medication_history_records", source.id.value
    )
    hidden_draft = create_record(
        corporate_id=source.corporate_id,
        store_id=source.store_id,
        patient_id=source.patient_id,
        dispensing_id=source.dispensing_id,
        prescription_id=source.prescription_id,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).medication_history.save(hidden_draft)
        await work.commit()
    operator = await _save_store_operator(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        candidates = await client.get(
            f"/corporates/{clinical.corporate_id.value}"
            f"/patients/{source.patient_id.value}/medication-histories/follow-up-sources",
            params={"store_id": str(operator.store.id.value)},
        )
        body = _follow_up_body(operator)
        body["patient_id"] = str(source.patient_id.value)
        created = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{source.id.value}/follow-ups",
            json=body,
        )
        assert created.status_code == 201, created.text
        follow_up_id = created.json()["id"]
        one = await client.get(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{follow_up_id}"
        )
        listed = await client.get(
            f"/corporates/{clinical.corporate_id.value}"
            f"/patients/{source.patient_id.value}/medication-histories"
        )
        hidden_source = await client.get(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{source.id.value}"
        )
        hidden_draft_body = _follow_up_body(operator)
        hidden_draft_body["patient_id"] = str(source.patient_id.value)
        hidden_draft_response = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{hidden_draft.id.value}/follow-ups",
            json=hidden_draft_body,
        )

    assert candidates.status_code == 200, candidates.text
    assert [item["record_id"] for item in candidates.json()] == [str(source.id.value)]
    assert one.status_code == 200, one.text
    assert one.json()["store_id"] == str(operator.store.id.value)
    assert one.json()["source_record_id"] == str(source.id.value)
    assert one.json()["soap"]["subjective"][0]["text"] == "服用後の変化を確認した。"
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [follow_up_id]
    assert hidden_source.status_code == 404
    assert hidden_draft_response.status_code == 404
    assert await _count(engine, "medication_history_records") == 3
    assert (
        await _version(engine, "medication_history_records", source.id.value)
        == source_version
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        unchanged_source = await repositories.medication_history.get(
            corporate_id=clinical.corporate_id,
            record_id=source.id,
        )
        source_profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=source.patient_id,
        )
    assert unchanged_source is not None
    assert unchanged_source.soap == source.soap
    assert unchanged_source.status is MedicationHistoryStatus.FINALIZED
    assert source_profile is not None

    async with engine.connect() as connection:
        audit = (
            await connection.execute(
                text(
                    "SELECT person_id, account_id, corporate_id, store_id "
                    "FROM operation_audits WHERE resource_id = :resource_id"
                ),
                {"resource_id": UUID(follow_up_id)},
            )
        ).one()
    assert audit[0] == operator.person.id.value
    assert audit[1] == operator.account.id.value
    assert audit[2] == clinical.corporate_id.value
    assert audit[3] == operator.store.id.value


@pytest.mark.asyncio
async def test_tc47_店舗オペレータは頭書きを再構築できず_法人管理者は全店舗を反映する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """再構築は法人範囲で認可し、A店とB店の確定差分を再集約する。"""
    clinical = await setup_clinical(engine, session_factory)
    source = await _finalize_initial(clinical, session_factory)
    operator = await _save_store_operator(
        engine,
        session_factory,
        corporate_id=clinical.corporate_id,
        clock=FakeClock(datetime(2026, 9, 22, 3, tzinfo=UTC)),
    )
    body = _follow_up_body(operator)
    body["patient_id"] = str(source.patient_id.value)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        created = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{source.id.value}/follow-ups",
            json=body,
        )
    assert created.status_code == 201, created.text
    follow_up_id = created.json()["id"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        finalized = await client.post(
            f"/corporates/{clinical.corporate_id.value}"
            f"/medication-histories/{follow_up_id}/finalization",
            json={
                "review_result": "assessment_and_instruction_recorded",
                "delay_reason": "患者への後日確認のため翌日確定",
            },
        )
    assert finalized.status_code == 200, finalized.text

    rebuild_path = (
        f"/corporates/{clinical.corporate_id.value}/patients/"
        f"{source.patient_id.value}/medical-profile/rebuild"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=operator.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        denied = await client.post(rebuild_path, json={"as_of": "2026-09-22"})
    assert denied.status_code == 403, denied.text

    admin_app = await _save_corporate_admin(
        engine, session_factory, corporate_id=clinical.corporate_id
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=admin_app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        rebuilt = await client.post(rebuild_path, json={"as_of": "2026-09-22"})
    assert rebuilt.status_code == 200, rebuilt.text
    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=clinical.corporate_id,
            patient_id=source.patient_id,
        )
    assert profile is not None
    assert {item.allergen.value for item in profile.allergies} == {
        "ペニシリン系",
        "そば",
    }


async def _saved_cross_store_pair(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[MedicationHistoryRecord, MedicationHistoryRecord]:
    """別店舗参照が有効な初回薬歴と独立フォローアップを保存する。"""
    source = finalize_record_with_review(
        create_record(
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(),)
            )
        )
    )
    follow_up = create_independent_follow_up_record(
        source,
        store_id=create_store(corporate_id=source.corporate_id, name="参照先店舗").id,
        finalized=True,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        await repository.save(source)
        await repository.save(follow_up)
        await work.commit()
    return source, follow_up


@pytest.mark.asyncio
async def test_tc41_follow_up複合外部キーが参照元と法人患者処方調剤の一致を守る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """店舗は異なってよいが、参照する薬歴と患者・処方・調剤は一致させる。"""
    source, follow_up = await _saved_cross_store_pair(session_factory)
    assert source.store_id != follow_up.store_id

    invalid_updates: tuple[tuple[str, dict[str, object]], ...] = (
        ("source_record_id = :value", {"value": uuid4()}),
        ("corporate_id = :value", {"value": uuid4()}),
        ("patient_id = :value", {"value": uuid4()}),
        ("prescription_id = :value", {"value": uuid4()}),
        ("dispensing_id = :value", {"value": uuid4()}),
    )
    for assignment, values in invalid_updates:
        async with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                await connection.execute(
                    text(
                        f"UPDATE medication_history_records SET {assignment} "
                        "WHERE id = :record_id"
                    ),
                    {**values, "record_id": follow_up.id.value},
                )


@pytest.mark.asyncio
async def test_tc42_薬歴種別と参照元の組み合わせをDBのCHECK制約で守る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """初回に参照元を付ける変更とフォローアップ参照を外す変更を拒否する。"""
    source, follow_up = await _saved_cross_store_pair(session_factory)
    invalid_updates = (
        "record_kind = 'initial'",
        "source_record_id = NULL",
    )
    for assignment in invalid_updates:
        async with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                await connection.execute(
                    text(
                        f"UPDATE medication_history_records SET {assignment} "
                        "WHERE id = :record_id"
                    ),
                    {"record_id": follow_up.id.value},
                )
    async with PostgresUnitOfWork(session_factory) as work:
        stored_source = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=source.corporate_id,
            record_id=source.id,
        )
    assert stored_source is not None
