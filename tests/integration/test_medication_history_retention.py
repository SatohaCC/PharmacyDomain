"""薬歴の保存期限更新がPostgreSQL上で原子的かつ並行安全であることを検証する。"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.common.clock import Clock
from app.domain.dispensing.primitives import DispensingCompletionTimestamp
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.shared.preservation import (
    PreservationPolicyCatalog,
    PreservationRecordKind,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.factories.medication_history_factory import (
    create_adverse_reaction_intent,
    create_record,
    finalize_record_with_review,
)
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.test_clinical_transaction_http import (
    ClinicalFixture,
    _client,
    _count,
    reject_profile_writes,
    setup_clinical,
)


class _TaskAwareClock(Clock):
    """並行HTTP要求ごとに異なる確定日時を返す。"""

    def __init__(self, *, default: datetime, task_times: dict[str, datetime]) -> None:
        self._default = default
        self._task_times = task_times
        self._request_time: ContextVar[datetime | None] = ContextVar(
            "medication_history_retention_request_time", default=None
        )

    @contextmanager
    def for_current_request(
        self, request_time: datetime | None = None
    ) -> Iterator[None]:
        """要求の日時をHTTPミドルウェア配下のタスクへ伝播する。"""
        selected_time = request_time
        if selected_time is None:
            task = asyncio.current_task()
            selected_time = (
                self._task_times.get(task.get_name(), self._default)
                if task is not None
                else self._default
            )
        token = self._request_time.set(selected_time)
        try:
            yield
        finally:
            self._request_time.reset(token)

    def now(self) -> datetime:
        """現在のasyncioタスクに割り当てたaware UTC日時を返す。"""
        request_time = self._request_time.get()
        if request_time is not None:
            return request_time
        task = asyncio.current_task()
        if task is None:
            return self._default
        return self._task_times.get(task.get_name(), self._default)


def _finalization_url(
    fixture: ClinicalFixture, record_id: MedicationHistoryRecordId
) -> str:
    """薬歴確定エンドポイントのURLを返す。"""
    return (
        f"/corporates/{fixture.corporate_id.value}"
        f"/medication-histories/{record_id.value}/finalization"
    )


async def _finalize(
    fixture: ClinicalFixture,
    record_id: MedicationHistoryRecordId,
    *,
    request_time: datetime | None = None,
    delay_reason: str | None = None,
) -> httpx.Response:
    """HTTP経由で薬歴を確定する。"""
    state = getattr(fixture.app.state, STATE_ATTRIBUTE, None)
    assert isinstance(state, PresentationState)
    assert state.composition_root is not None
    clock = state.composition_root.clock

    async def post() -> httpx.Response:
        async with _client(fixture) as client:
            body = {"review_result": "assessment_and_instruction_recorded"}
            if delay_reason is not None:
                body["delay_reason"] = delay_reason
            return await client.post(
                _finalization_url(fixture, record_id),
                json=body,
            )

    if isinstance(clock, _TaskAwareClock):
        with clock.for_current_request(request_time):
            return await post()
    assert request_time is None
    return await post()


@pytest.mark.asyncio
async def test_tc40_11_保存起算情報はPostgreSQL再読込後も保持される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """処方箋の調剤済日と調剤録の完了時刻・業務日をJSONBから復元する。"""
    fixture = await setup_clinical(engine, session_factory)
    completed_at = datetime(2026, 9, 26, 16, 30, tzinfo=UTC)
    completed_on = date(2026, 9, 27)

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        current_prescription = await repositories.prescription.get(
            corporate_id=fixture.corporate_id,
            prescription_id=fixture.prescription.id,
        )
        current_process = await repositories.dispensing.get(
            corporate_id=fixture.corporate_id,
            dispensing_id=fixture.process.id,
        )
        assert current_prescription is not None
        assert current_process is not None
        await repositories.prescription.save(
            replace(current_prescription, dispensed_on=date(2026, 9, 24))
        )
        await repositories.dispensing.save(
            replace(
                current_process,
                completed_at=DispensingCompletionTimestamp(completed_at),
                completed_on=completed_on,
            )
        )
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        restored_prescription = await repositories.prescription.get(
            corporate_id=fixture.corporate_id,
            prescription_id=fixture.prescription.id,
        )
        restored_process = await repositories.dispensing.get(
            corporate_id=fixture.corporate_id,
            dispensing_id=fixture.process.id,
        )

    assert restored_prescription is not None
    assert restored_prescription.dispensed_on == date(2026, 9, 24)
    assert restored_process is not None
    assert restored_process.completed_at == DispensingCompletionTimestamp(completed_at)
    assert restored_process.completed_on == completed_on
    catalog = PreservationPolicyCatalog.create_standard_statutory_catalog(
        PreservationRecordKind.DISPENSING_RECORD
    )
    assert restored_process.calculate_retention_expiry_date(catalog) == date(
        2029, 9, 27
    )


@pytest.mark.asyncio
async def test_tc40_09_期限更新と頭書き保存の失敗で患者内更新を巻き戻す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """過去薬歴の延伸・新規確定・頭書き投影を同じトランザクションにする。"""
    clock = FakeClock(datetime(2026, 9, 25, 3, tzinfo=UTC))
    fixture = await setup_clinical(engine, session_factory, clock=clock)
    old_counseled_at = datetime(2024, 1, 10, 3, tzinfo=UTC)
    old_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.record.store_id,
            patient_id=fixture.record.patient_id,
            counselor_id=fixture.record.counselor_id,
            counseled_at=old_counseled_at,
        ),
        finalized_at=FinalizedTimestamp(old_counseled_at),
    )
    old_record = replace(
        old_record,
        dispensing_id=None,
        prescription_id=None,
        retention_expiry_date=date(2027, 1, 10),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await save_history_with_event(PostgresRepositorySet.create(work), old_record)
        await work.commit()

    async with reject_profile_writes(engine):
        failed = await _finalize(fixture, fixture.record.id)

    assert failed.status_code == 500, failed.text
    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        stored_old = await repository.get(
            corporate_id=fixture.corporate_id, record_id=old_record.id
        )
        stored_new = await repository.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
    assert stored_old is not None
    assert stored_old.retention_expiry_date == date(2027, 1, 10)
    assert stored_new is not None
    assert stored_new.status is MedicationHistoryStatus.DRAFT
    assert stored_new.retention_expiry_date is None
    assert await _count(engine, "patient_medical_profiles") == 0
    assert await _count(engine, "operation_audits") == 0

    retried = await _finalize(fixture, fixture.record.id)
    assert retried.status_code == 200, retried.text
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_old = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=old_record.id
        )
        stored_new = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.record.patient_id,
        )
    assert stored_old is not None
    assert stored_old.retention_expiry_date == date(2029, 9, 25)
    assert stored_new is not None
    assert stored_new.status is MedicationHistoryStatus.FINALIZED
    assert stored_new.retention_expiry_date == date(2029, 9, 25)
    assert profile is not None


@pytest.mark.asyncio
async def test_tc40_10_患者内の並行確定は後の日付の期限へ収束する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """確定順が逆転しても、同一患者の全薬歴が最新記入日を保持する。"""
    earlier = datetime(2026, 9, 25, 3, tzinfo=UTC)
    later = datetime(2026, 9, 26, 3, tzinfo=UTC)
    clock = _TaskAwareClock(
        default=earlier,
        task_times={"finalize-earlier": earlier, "finalize-later": later},
    )
    fixture = await setup_clinical(engine, session_factory, clock=clock)
    second_record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.record.store_id,
        patient_id=fixture.record.patient_id,
        counselor_id=fixture.record.counselor_id,
        counseled_at=earlier,
    )
    second_record = replace(
        second_record,
        dispensing_id=None,
        prescription_id=None,
        profile_updates=ProfileUpdateIntents(
            new_adverse_reactions=(create_adverse_reaction_intent(),)
        ),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await save_history_with_event(PostgresRepositorySet.create(work), second_record)
        await work.commit()

    earlier_task = asyncio.create_task(
        _finalize(fixture, fixture.record.id), name="finalize-earlier"
    )
    later_task = asyncio.create_task(
        _finalize(
            fixture,
            second_record.id,
            delay_reason="並行確定テストで後日確定するため。",
        ),
        name="finalize-later",
    )
    responses = await asyncio.gather(earlier_task, later_task)
    assert all(response.status_code in {200, 409} for response in responses), [
        (response.status_code, response.text) for response in responses
    ]
    assert any(response.status_code == 200 for response in responses)

    for record_id, response in zip(
        (fixture.record.id, second_record.id), responses, strict=True
    ):
        if response.status_code == 409:
            retry_time = earlier if record_id == fixture.record.id else later
            retry_reason = (
                "並行確定テストで後日確定するため。"
                if record_id == second_record.id
                else None
            )
            retry = await _finalize(
                fixture,
                record_id,
                request_time=retry_time,
                delay_reason=retry_reason,
            )
            assert retry.status_code == 200, retry.text

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        finalized_records = [
            await repository.get(corporate_id=fixture.corporate_id, record_id=record_id)
            for record_id in (fixture.record.id, second_record.id)
        ]
    assert all(
        record is not None and record.status is MedicationHistoryStatus.FINALIZED
        for record in finalized_records
    )
    assert [
        record.retention_expiry_date
        for record in finalized_records
        if record is not None
    ] == [date(2029, 9, 26), date(2029, 9, 26)]


@pytest.mark.asyncio
async def test_tc40_06_07_店舗ロールでも法人内別店舗の薬歴期限を延伸する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """店舗ロールで確定しても、患者内の他店舗記録まで期限を更新する。"""
    clock = FakeClock(datetime(2026, 9, 25, 3, tzinfo=UTC))
    fixture = await setup_clinical(engine, session_factory, clock=clock)
    other_store = create_store(
        corporate_id=fixture.corporate_id,
        name="別店舗",
        kana="ベツテンポ",
    )
    old_written_at = datetime(2024, 1, 10, 3, tzinfo=UTC)
    old_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=other_store.id,
            patient_id=fixture.record.patient_id,
            counselor_id=fixture.record.counselor_id,
            counseled_at=old_written_at,
        ),
        finalized_at=FinalizedTimestamp(old_written_at),
    )
    old_record = replace(
        old_record,
        dispensing_id=None,
        prescription_id=None,
        retention_expiry_date=date(2027, 1, 10),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.store.save(other_store)
        await save_history_with_event(repositories, old_record)
        await work.commit()

    response = await _finalize(fixture, fixture.record.id)
    assert response.status_code == 200, response.text

    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).medication_history
        stored_old = await repository.get(
            corporate_id=fixture.corporate_id,
            record_id=old_record.id,
        )
        stored_new = await repository.get(
            corporate_id=fixture.corporate_id,
            record_id=fixture.record.id,
        )

    assert stored_old is not None
    assert stored_old.retention_expiry_date == date(2029, 9, 25)
    assert stored_new is not None
    assert stored_new.retention_expiry_date == date(2029, 9, 25)
