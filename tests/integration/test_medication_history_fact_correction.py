"""薬歴事実訂正の HTTP・PostgreSQL 境界を実データで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    CounselingMethod,
    CounselingTimestamp,
    FinalizationDelayReason,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.store.lifecycle import StoreStatus, StoreStatusReason
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.domain.medication_history.test_fact_correction import _correct, _element_id
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_concurrent_intent,
    create_independent_follow_up_record,
    create_stop_intent,
)
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    setup_clinical,
)

_ROUTE = "/corporates/{corporate_id}/medication-histories/{record_id}/corrections"


def _url(fixture: ClinicalFixture, record_id: object | None = None) -> str:
    selected_id = record_id if record_id is not None else fixture.record.id.value
    return (
        f"/corporates/{fixture.corporate_id.value}"
        f"/medication-histories/{selected_id}/corrections"
    )


def _require_route(fixture: ClinicalFixture) -> None:
    """欠落ルートの 404 をテナント隠蔽の成功と誤認しない。"""
    assert "post" in fixture.app.openapi()["paths"].get(_ROUTE, {}), (
        "事実訂正ルートが必要"
    )


async def _finalize(fixture: ClinicalFixture) -> None:
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/medication-histories/{fixture.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )
    assert response.status_code == 200, response.text


async def _read_record(
    session_factory: async_sessionmaker[AsyncSession], fixture: ClinicalFixture
) -> MedicationHistoryRecord | None:
    async with PostgresUnitOfWork(session_factory) as work:
        return await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )


async def _version(engine: AsyncEngine, record_id: object) -> int:
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(
                    text("SELECT version FROM medication_history_records WHERE id=:id"),
                    {"id": record_id},
                )
            ).scalar_one()
        )


async def test_tc28_後続Intentが無効になる訂正は両集約とも巻き戻る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        draft = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        assert draft is not None
        await repositories.medication_history.save(
            replace(
                draft,
                profile_updates=ProfileUpdateIntents(
                    new_concurrent_medications=(create_concurrent_intent(),)
                ),
            )
        )
        await work.commit()
    await _finalize(fixture)
    first = await _read_record(session_factory, fixture)
    assert first is not None
    assert first.counseled_at is not None
    later = create_independent_follow_up_record(
        first,
        counseled_at=first.counseled_at.value + timedelta(days=1),
        finalized=True,
        profile_updates=ProfileUpdateIntents(
            stopped_concurrent_medications=(create_stop_intent(),)
        ),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await save_history_with_event(repositories, later)
        existing_profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=first.patient_id,
        )
        assert existing_profile is not None
        await repositories.patient_medical_profile.save(
            replace(
                PatientMedicalProfile.rebuild_from(
                    corporate_id=fixture.corporate_id,
                    patient_id=first.patient_id,
                    records=(first, later),
                ),
                id=existing_profile.id,
            )
        )
        await work.commit()
    version_before = await _version(engine, first.id.value)
    target = _element_id(first, "profile_updates.new_concurrent_medications", 0)
    _require_route(fixture)

    async with _client(fixture) as client:
        response = await client.post(
            _url(fixture),
            json={
                "target": target,
                "operation": "retract",
                "reason": "開始記録の誤りを訂正した。",
            },
        )

    assert response.status_code == 404, response.text
    assert await _version(engine, first.id.value) == version_before
    stored = await _read_record(session_factory, fixture)
    assert stored is not None
    assert stored.fact_corrections == ()
    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=first.patient_id
        )
    assert profile is not None
    assert len(profile.concurrent_medications) == 1
    assert profile.concurrent_medications[0].ended_on is not None


@pytest.mark.parametrize("boundary", ("corporate", "store"))
async def test_tc32_他法人と対象外店舗の薬歴は存在を隠す(
    boundary: str,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    target_id = fixture.record.id.value
    corporate_id = fixture.corporate_id
    if boundary == "corporate":
        other = create_corporate("別法人")
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresRepositorySet.create(work).corporate.save(other)
            await work.commit()
        corporate_id = other.id
    else:
        other_store = create_store(
            corporate_id=fixture.corporate_id,
            name="別店舗薬局",
            kana="ベッテンポヤッキョク",
        )
        first = await _read_record(session_factory, fixture)
        assert first is not None
        other_record = create_independent_follow_up_record(
            first, store_id=other_store.id, finalized=True
        )
        async with PostgresUnitOfWork(session_factory) as work:
            repositories = PostgresRepositorySet.create(work)
            await repositories.store.save(other_store)
            await save_history_with_event(repositories, other_record)
            await work.commit()
        target_id = other_record.id.value
    _require_route(fixture)

    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{corporate_id.value}"
            f"/medication-histories/{target_id}/corrections",
            json={
                "target": "information_sheet_provided",
                "operation": "replace",
                "value": True,
                "reason": "原記録の誤りを確認した。",
            },
        )

    assert response.status_code == 404, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        target = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id,
            record_id=(
                fixture.record.id if boundary == "corporate" else other_record.id
            ),
        )
    assert target is not None
    assert target.fact_corrections == ()


async def test_tc38_訂正後の指導日時を検索列と一覧順序へ反映する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    first = await _read_record(session_factory, fixture)
    assert first is not None
    assert first.counseled_at is not None
    other = create_independent_follow_up_record(
        first,
        counseled_at=first.counseled_at.value - timedelta(days=1),
        finalized=True,
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await save_history_with_event(repositories, other)
        await work.commit()
    corrected_time = CounselingTimestamp(first.counseled_at.value - timedelta(days=2))
    with_reason = _correct(
        first,
        target="delay_reason",
        value=FinalizationDelayReason("後日確定した記録の指導日を訂正した。"),
    )
    corrected = _correct(with_reason, target="counseled_at", value=corrected_time)

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        loaded_before_save = await repository.get(
            corporate_id=fixture.corporate_id, record_id=first.id
        )
        assert loaded_before_save is not None
        await repository.save(corrected)
        await work.commit()
    async with engine.connect() as connection:
        indexed_time = (
            await connection.execute(
                text(
                    "SELECT counseled_at FROM medication_history_records WHERE id=:id"
                ),
                {"id": first.id.value},
            )
        ).scalar_one()
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        loaded = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=first.id
        )
        timeline = await repositories.medication_history.list_by_patient(
            corporate_id=fixture.corporate_id, patient_id=first.patient_id
        )

    assert indexed_time == corrected_time.value
    assert loaded is not None
    assert loaded.effective_facts.counseled_at == corrected_time
    assert [item.id for item in timeline] == [first.id, other.id]


async def test_tc40_同じ世代を読んだ後続訂正は競合で失敗する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    slow = PostgresUnitOfWork(session_factory)
    async with slow:
        slow_repositories = PostgresRepositorySet.create(slow)
        stale = await slow_repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        assert stale is not None
        async with PostgresUnitOfWork(session_factory) as fast:
            fast_repositories = PostgresRepositorySet.create(fast)
            fresh = await fast_repositories.medication_history.get(
                corporate_id=fixture.corporate_id, record_id=fixture.record.id
            )
            assert fresh is not None
            allergy_id = _element_id(fresh, "profile_updates.new_allergies", 0)
            winner = _correct(
                fresh,
                target=allergy_id,
                value=create_allergy_intent(reaction="蕁麻疹"),
            )
            await fast_repositories.medication_history.save(winner)
            previous_profile = (
                await fast_repositories.patient_medical_profile.get_by_patient(
                    corporate_id=fixture.corporate_id,
                    patient_id=fixture.record.patient_id,
                )
            )
            assert previous_profile is not None
            await fast_repositories.patient_medical_profile.save(
                replace(
                    PatientMedicalProfile.rebuild_from(
                        corporate_id=fixture.corporate_id,
                        patient_id=fixture.record.patient_id,
                        records=(winner,),
                    ),
                    id=previous_profile.id,
                )
            )
            await fast.commit()

        with pytest.raises(ConcurrentModificationError):
            await slow_repositories.medication_history.save(
                _correct(stale, target="method", value=CounselingMethod.TELEPHONE)
            )

    assert await _version(engine, fixture.record.id.value) == 3
    saved = await _read_record(session_factory, fixture)
    assert saved is not None
    assert len(saved.fact_corrections) == 1
    effective_facts = getattr(saved, "effective_facts", None)
    assert effective_facts is not None
    assert effective_facts.profile_updates.new_allergies[0].reaction.value == "蕁麻疹"
    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
        )
    assert profile is not None
    assert profile.allergies[0].reaction.value == "蕁麻疹"


async def test_tc41_HTTPで要素IDを選んで訂正履歴と投影を読める(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    _require_route(fixture)
    read_url = (
        f"/corporates/{fixture.corporate_id.value}"
        f"/medication-histories/{fixture.record.id.value}"
    )
    async with _client(fixture) as client:
        before = await client.get(read_url)
        assert before.status_code == 200, before.text
        element_id = before.json()["profile_updates"]["new_allergies"][0]["id"]
        response = await client.post(
            _url(fixture),
            json={
                "target": element_id,
                "operation": "replace",
                "value": {
                    "allergen": "ペニシリン系",
                    "reaction": "蕁麻疹",
                    "severity": "moderate",
                },
                "reason": "患者の申告を再確認した。",
            },
        )
        after = await client.get(read_url)

    assert response.status_code == 201, response.text
    assert after.status_code == 200, after.text
    body = after.json()
    assert body["profile_updates"]["new_allergies"][0]["reaction"] == "蕁麻疹"
    assert (
        body["original_facts"]["profile_updates"]["new_allergies"][0]["reaction"]
        == "皮疹"
    )
    correction = body["fact_corrections"][0]
    assert correction["target"] == element_id
    assert correction["before"]["reaction"] == "皮疹"
    assert correction["after"]["reaction"] == "蕁麻疹"
    assert correction["reason"] == "患者の申告を再確認した。"
    assert correction["corrected_by"]
    assert correction["recorded_at"]
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        record = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.record.patient_id
        )
    assert record is not None
    assert profile is not None
    assert (
        profile.allergies
        == PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
            records=(record,),
        ).allergies
    )


@pytest.mark.parametrize(
    "body",
    (
        {"target": "soap", "operation": "replace", "value": "変更", "reason": "誤記"},
        {
            "target": "method",
            "element_id": "別の対象",
            "operation": "replace",
            "value": "telephone",
            "reason": "誤記",
        },
        {"target": "method", "operation": "replace", "reason": "誤記"},
        {
            "target": "method",
            "operation": "replace",
            "value": "telephone",
            "reason": "誤記",
            "corrected_by": "任意の別人",
        },
        {
            "target": "method",
            "operation": "append",
            "value": "telephone",
            "reason": "誤記",
        },
    ),
)
async def test_tc42_HTTPの不正対象と余分な監査入力を拒否する(
    body: dict[str, object],
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    _require_route(fixture)

    async with _client(fixture) as client:
        response = await client.post(_url(fixture), json=body)

    assert response.status_code == 422, response.text
    stored = await _read_record(session_factory, fixture)
    assert stored is not None
    assert stored.fact_corrections == ()


@pytest.mark.parametrize(
    ("status", "expected_code"),
    ((StoreStatus.SUSPENDED, 201), (StoreStatus.CLOSED, 409)),
)
async def test_tc47_休止店舗の継続訂正は許可し閉局店舗は拒否する(
    status: StoreStatus,
    expected_code: int,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fixture = await setup_clinical(engine, session_factory)
    await _finalize(fixture)
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        store = await repositories.store.get(fixture.record.store_id)
        assert store is not None
        assert fixture.record.counseled_at is not None
        await repositories.store.save(
            store.change_status(
                status,
                reason=StoreStatusReason("店舗状態の検証"),
                person_id=fixture.person.id,
                account_id=fixture.account.id,
                recorded_at=fixture.record.counseled_at.value,
            )
        )
        await work.commit()
    _require_route(fixture)

    async with _client(fixture) as client:
        response = await client.post(
            _url(fixture),
            json={
                "target": "information_sheet_provided",
                "operation": "replace",
                "value": True,
                "reason": "患者の申告を再確認した。",
            },
        )

    assert response.status_code == expected_code, response.text
    stored = await _read_record(session_factory, fixture)
    assert stored is not None
    assert len(stored.fact_corrections) == (1 if status is StoreStatus.SUSPENDED else 0)
