"""患者頭書きのPostgreSQL永続化・監査・競合を検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.patient.change_patient_heading import ChangePatientHeadingCommand
from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.patient.heading import (
    PatientHeadingContent,
    PatientHeadingRevision,
    PatientHeadingText,
)
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientAddress, PatientId
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileChangeSource,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.presentational.dependencies import STATE_ATTRIBUTE
from tests.factories.persistence_factory import create_patient
from tests.factories.store_factory import create_store
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    setup_clinical,
)

_NOW = datetime(2026, 9, 20, 3, tzinfo=UTC)


def _revision(summary: str, notes: str | None = None) -> PatientHeadingRevision:
    """DB上の競合テストに使う改訂を作る。"""
    return PatientHeadingRevision(
        content=PatientHeadingContent(
            summary=PatientHeadingText(summary),
            notes=PatientHeadingText(notes) if notes is not None else None,
        ),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=_NOW,
    )


def _heading_url(fixture: ClinicalFixture) -> str:
    return (
        f"/corporates/{fixture.corporate_id.value}/patients/"
        f"{fixture.record.patient_id.value}/heading"
    )


async def _stored_patient(
    session_factory: async_sessionmaker[AsyncSession], fixture: ClinicalFixture
) -> Patient | None:
    async with PostgresUnitOfWork(session_factory) as work:
        return await PostgresRepositorySet.create(work).patient.get(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
        )


async def _version(engine: AsyncEngine, patient_id: PatientId) -> int:
    async with engine.connect() as connection:
        value = await connection.execute(
            text("SELECT version FROM patients WHERE id = :patient_id"),
            {"patient_id": patient_id.value},
        )
    return int(value.scalar_one())


async def _audit_count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        value = await connection.execute(text("SELECT count(*) FROM operation_audits"))
    return int(value.scalar_one())


async def test_tc43_39_HTTP更新をPostgreSQLへ保存し履歴つきで読み戻す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    async with _client(fixture) as client:
        response = await client.patch(
            _heading_url(fixture),
            json={
                "expected_revision": 0,
                "summary": "DBへ保存する概要",
                "notes": "DBへ保存する申し送り",
            },
        )
        assert response.status_code == 200, response.text
        reread = await client.get(_heading_url(fixture))

    assert reread.status_code == 200, reread.text
    assert reread.json()["revision"] == 1
    assert reread.json()["summary"] == "DBへ保存する概要"
    assert reread.json()["notes"] == "DBへ保存する申し送り"
    assert len(reread.json()["history"]) == 1
    stored = await _stored_patient(session_factory, fixture)
    assert stored is not None
    assert stored.heading_history[-1].content.summary == PatientHeadingText(
        "DBへ保存する概要"
    )
    revision = reread.json()["history"][0]
    assert revision["person_id"] == str(fixture.person.id.value)
    assert revision["account_id"] == str(fixture.account.id.value)
    assert datetime.fromisoformat(revision["recorded_at"]) == _NOW


async def test_tc43_40_頭書きと同じ本人の操作監査を記録する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    before = await _audit_count(engine)
    async with _client(fixture) as client:
        response = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 0, "summary": "監査対象"},
        )
    assert response.status_code == 200, response.text

    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT person_id, account_id, resource_id, corporate_id "
                    "FROM operation_audits "
                    "ORDER BY recorded_at DESC LIMIT 1"
                )
            )
        ).one()
    assert await _audit_count(engine) == before + 1
    assert row.person_id == fixture.person.id.value
    assert row.account_id == fixture.account.id.value
    assert row.resource_id == fixture.record.patient_id.value
    assert row.corporate_id == fixture.corporate_id.value


async def test_tc43_41_監査書込みに失敗した更新を一括rollbackする(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    original_version = await _version(engine, fixture.record.patient_id)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE operation_audits "
                "ADD CONSTRAINT test_reject_heading_audit CHECK (false)"
            )
        )
    state = getattr(fixture.app.state, STATE_ATTRIBUTE)
    root = state.composition_root
    assert root is not None
    actor = await state.actor_provider.authenticate(VALID_TOKEN)
    try:
        with pytest.raises(IntegrityError):
            async with root.request_scope(
                authorization=AuthorizationService(actor)
            ) as scope:
                await scope.use_cases.patient.change_heading.execute(
                    ChangePatientHeadingCommand(
                        corporate_id=str(fixture.corporate_id.value),
                        patient_id=str(fixture.record.patient_id.value),
                        expected_revision=0,
                        provided_fields=frozenset({"summary"}),
                        summary="監査失敗時の本文",
                    )
                )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "ALTER TABLE operation_audits "
                    "DROP CONSTRAINT test_reject_heading_audit"
                )
            )

    assert await _version(engine, fixture.record.patient_id) == original_version
    assert await _audit_count(engine) == 0
    stored = await _stored_patient(session_factory, fixture)
    assert stored is not None
    assert stored.heading_history == ()


async def test_tc43_42_同値更新はDB行と監査を追加しない(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    async with _client(fixture) as client:
        first = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 0, "summary": "同じ内容"},
        )
        assert first.status_code == 200, first.text
        version = await _version(engine, fixture.record.patient_id)
        audits = await _audit_count(engine)
        second = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 1, "summary": " 同じ内容 "},
        )

    assert second.status_code == 200, second.text
    assert second.json()["revision"] == 1
    assert await _version(engine, fixture.record.patient_id) == version
    assert await _audit_count(engine) == audits


async def test_tc43_43_古い改訂をHTTPで拒否しDBの現在値を保つ(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    async with _client(fixture) as client:
        first = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 0, "summary": "1回目の本文"},
        )
        assert first.status_code == 200, first.text
        second = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 1, "summary": "2回目の確定本文"},
        )
        assert second.status_code == 200, second.text
        stale = await client.patch(
            _heading_url(fixture),
            json={"expected_revision": 1, "summary": "古い本文"},
        )
        reread = await client.get(_heading_url(fixture))

    assert stale.status_code == 409
    assert stale.json()["code"] == "PATIENT_HEADING_CONFLICT"
    assert reread.json()["summary"] == "2回目の確定本文"
    assert reread.json()["revision"] == 2


async def test_tc43_44_同時に読んだ患者改訂はDBversionで競合する(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    patient_id = fixture.record.patient_id
    async with (
        PostgresUnitOfWork(session_factory) as first_work,
        PostgresUnitOfWork(session_factory) as stale_work,
    ):
        first_repositories = PostgresRepositorySet.create(first_work)
        stale_repositories = PostgresRepositorySet.create(stale_work)
        first_patient = await first_repositories.patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
        stale_patient = await stale_repositories.patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
        assert first_patient is not None
        assert stale_patient is not None
        first_update = first_patient.change_heading(
            PatientHeadingContent(summary=PatientHeadingText("先行"), notes=None),
            expected_revision=0,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=_NOW,
        )
        stale_update = stale_patient.change_heading(
            PatientHeadingContent(summary=PatientHeadingText("競合"), notes=None),
            expected_revision=0,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=_NOW,
        )
        await first_repositories.patient.save(first_update)
        await first_work.commit()
        with pytest.raises(ConcurrentModificationError):
            await stale_repositories.patient.save(stale_update)
        await stale_work.rollback()

    async with PostgresUnitOfWork(session_factory) as work:
        stored = await PostgresRepositorySet.create(work).patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
    assert stored is not None
    assert len(stored.heading_history) == 1
    assert stored.heading_history[0].content.summary == PatientHeadingText("先行")

    async with (
        PostgresUnitOfWork(session_factory) as profile_work,
        PostgresUnitOfWork(session_factory) as stale_heading_work,
    ):
        profile_repositories = PostgresRepositorySet.create(profile_work)
        stale_heading_repositories = PostgresRepositorySet.create(stale_heading_work)
        profile_read = await profile_repositories.patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
        stale_heading_read = await stale_heading_repositories.patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
        assert profile_read is not None
        assert stale_heading_read is not None
        before_profile = profile_read.profile_snapshot()
        updated_profile = replace(
            before_profile, address=PatientAddress("東京都港区新住所")
        )
        profile_update = profile_read.change_profile(
            updated_profile
        ).record_profile_change(
            PatientProfileChange(
                recorded_at=_NOW,
                changed_fields=("patient.address",),
                source=PatientProfileChangeSource.MANUAL,
                before_profile=before_profile,
                applied_profile=updated_profile,
                person_id=AccountPersonId.generate(),
                account_id=UserAccountId.generate(),
            )
        )
        stale_heading_update = stale_heading_read.change_heading(
            PatientHeadingContent(
                summary=PatientHeadingText("プロフィール更新後に再適用"),
                notes=None,
            ),
            expected_revision=1,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=_NOW,
        )
        await profile_repositories.patient.save(profile_update)
        await profile_work.commit()
        with pytest.raises(ConcurrentModificationError):
            await stale_heading_repositories.patient.save(stale_heading_update)
        await stale_heading_work.rollback()

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        latest = await repositories.patient.get(
            corporate_id=fixture.corporate_id, patient_id=patient_id
        )
        assert latest is not None
        reapplied_heading = latest.change_heading(
            PatientHeadingContent(
                summary=PatientHeadingText("プロフィール更新後に再適用"),
                notes=None,
            ),
            expected_revision=1,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=_NOW,
        )
        await repositories.patient.save(reapplied_heading)
        await work.commit()
    assert reapplied_heading.address == PatientAddress("東京都港区新住所")
    assert len(reapplied_heading.profile_history) == 1
    assert len(reapplied_heading.heading_history) == 2


async def test_tc43_45_法人内患者は店舗ロールから共有され他法人は隠す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    second_store = create_store(
        corporate_id=fixture.corporate_id,
        name="頭書き共有先薬局",
        kana="トウショガキキョウユウサキヤッキョク",
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).store.save(second_store)
        await work.commit()
    other_corporate = create_corporate("別法人頭書き")
    other_patient = create_patient(corporate_id=other_corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(other_corporate)
        await repositories.patient.save(other_patient)
        await work.commit()

    state = getattr(fixture.app.state, STATE_ATTRIBUTE)
    second_store_actor = ResolvedActorContext(
        principal_id="同法人の別店舗スタッフ",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        person_id=fixture.person.id,
        account_id=fixture.account.id,
        corporate_id=fixture.corporate_id,
        store_ids=frozenset({second_store.id}),
    )
    provider = StubActorContextProvider(second_store_actor)
    setattr(
        fixture.app.state,
        STATE_ATTRIBUTE,
        replace(state, actor_provider=provider),
    )

    async with _client(fixture) as client:
        in_corporate = await client.get(_heading_url(fixture))
        foreign = await client.get(
            f"/corporates/{other_corporate.id.value}/patients/"
            f"{other_patient.id.value}/heading"
        )

    assert in_corporate.status_code == 200
    assert foreign.status_code == 404
