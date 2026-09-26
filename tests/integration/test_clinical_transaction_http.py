"""2集約を書く業務更新が、HTTP経由でも1トランザクションであることを固定する。

調剤完了（調剤＋処方箋）と薬歴確定（薬歴＋頭書き）は、片方だけが残ると
「調剤済の処方箋に調剤の記録が無い」「根拠の無い頭書きだけが残る」という、
どちらも復旧に人手が要る状態になる。

既存の ``test_complete_dispensing_transaction.py`` は Composition Root を直接
呼んでおり、**HTTPルータ → ``get_request_scope`` → 同じ Unit of Work →
確定/破棄**という経路そのものは一度も通っていなかった。トランザクション境界を
握るのは ``PostgresRequestScope`` で、それを開くのは FastAPI の依存である。
配線が正しいことは、その依存を通してみるまで確かめられない。

失敗は**2つの書き込みのちょうど間**で起こす必要がある。薬歴側は頭書きの一意
制約では作れない（``_project_to_profile`` は先に ``get_by_patient()`` を引き、
既存行があればその ``id`` を引き継いで更新するので衝突しない）。そこで
``patient_medical_profiles`` へ一時的な ``CHECK (false)`` を張る。
``test_operation_audit.py`` が ``operation_audits`` に対して使っているのと
同じやり方である。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingProcessStatus
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
from app.domain.medication_history.primitives import MedicationHistoryStatus
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import PrescriptionStatus
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.presentational.app_factory import create_app
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.factories.dispensing_factory import create_dispensing, verify_passed
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_record,
)
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.test_identity_persistence import _person

#: 一時的に張る拒否制約の名前。後始末できたことを名前で確かめる。
_REJECT_PROFILE_CONSTRAINT = "test_reject_profile_writes"
_PHARMACIST_SUBJECT = "issuer/integration-clinical-pharmacist"

_CLOCK = FakeClock(datetime(2026, 9, 20, 3, tzinfo=UTC))


@dataclass(frozen=True, slots=True)
class ClinicalFixture:
    """HTTP経由の業務更新に必要な、実DB上の前提一式。"""

    app: FastAPI
    corporate_id: CorporateId
    person: AccountPerson
    account: UserAccount
    prescription: Prescription
    process: DispensingProcess
    record: MedicationHistoryRecord


async def setup_clinical(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    with_prescription: bool = True,
) -> ClinicalFixture:
    """法人・有効な店舗・本人・アカウントと、臨床の3集約を保存する。

    ``with_prescription`` を ``False`` にすると、調剤完了時に処方箋の更新だけが
    失敗する状態を作れる。

    管理薬剤師は任命しない。調剤完了（``RECORD_DISPENSING``）も薬歴確定
    （``AMEND_HISTORY``）も ``CONTINUING`` 区分で、``MANAGER_REQUIRED_BY_KIND``
    は在任を要求しないからである。要らない前提を置くと、テストが確かめている
    つもりのものが分からなくなる。
    """
    corporate = create_corporate("臨床トランザクション薬局")
    store = create_store(corporate_id=corporate.id)
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey(_PHARMACIST_SUBJECT),
    )
    # 受付済のままでは調剤済へ遷移できない。実運用でも調剤開始前に確定させる。
    prescription = replace(
        create_prescription(corporate_id=corporate.id).ready_for_dispensing(),
        store_id=store.id,
    )
    process = replace(
        verify_passed(
            create_dispensing(
                corporate_id=corporate.id, prescription_id=prescription.id
            )
        ),
        store_id=store.id,
    )
    pharmacist = replace(
        create_staff(corporate_id=corporate.id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
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
        corporate_id=corporate.id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({store.id}),
        staff_id=pharmacist.id,
    )
    record = create_record(
        corporate_id=corporate.id,
        store_id=store.id,
        counselor_id=pharmacist.id,
        counseled_at=_CLOCK.now(),
        # 差分が空でも頭書きは保存されるが、それでは「何が投影されたか」を
        # 確かめられない。アレルギーを1件持たせる。
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),)),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(corporate)
        await repositories.store.save(store)
        await repositories.account_person.save(person)
        await repositories.user_account.save(account)
        await repositories.staff.save(pharmacist)
        await repositories.staff_person_link.save(
            StaffPersonLink(
                id=pharmacist.id,
                corporate_id=corporate.id,
                person_id=person.id,
            )
        )
        await repositories.membership.save(membership)
        if with_prescription:
            await repositories.prescription.save(prescription)
        await repositories.dispensing.save(process)
        await repositories.medication_history.save(record)
        await work.commit()

    return ClinicalFixture(
        app=_clinical_app(
            engine,
            session_factory,
            person=person,
            account=account,
            membership=membership,
        ),
        corporate_id=corporate.id,
        person=person,
        account=account,
        prescription=prescription,
        process=process,
        record=record,
    )


def _clinical_app(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    person: AccountPerson,
    account: UserAccount,
    membership: CorporateMembership,
) -> FastAPI:
    """本番の組み立てを使い、認証だけを固定した操作主体へ差し替える。"""
    provider = StubActorContextProvider(
        ResolvedActorContext(
            principal_id=_PHARMACIST_SUBJECT,
            roles=frozenset({ActorRole.STORE_OPERATOR}),
            person_id=person.id,
            account_id=account.id,
            membership_id=membership.id,
            corporate_id=membership.corporate_id,
            staff_id=membership.staff_id,
            store_ids=membership.store_ids,
        )
    )
    app = create_app(actor_provider=provider)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=provider,
            composition_root=PostgresCompositionRoot(engine, session_factory, _CLOCK),
        ),
    )
    return app


def _client(fixture: ClinicalFixture) -> httpx.AsyncClient:
    """翻訳されない例外も応答として受け取るクライアント。

    ``IntegrityError`` は ``errors.py`` の翻訳表に無いので 500 になる。既定の
    ``ASGITransport`` は例外をそのまま送出するため、応答として観測できない。
    """
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fixture.app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )


@asynccontextmanager
async def reject_profile_writes(engine: AsyncEngine) -> AsyncIterator[None]:
    """頭書きの保存だけを必ず失敗させる。

    2つの書き込みの**間**で失敗させる唯一の確実な手段である。落とし忘れると
    以後の結合テストが全部落ちるので、``finally`` で必ず外す。
    """
    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"ALTER TABLE patient_medical_profiles "
                f"ADD CONSTRAINT {_REJECT_PROFILE_CONSTRAINT} CHECK (false)"
            )
        )
    try:
        yield
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    f"ALTER TABLE patient_medical_profiles "
                    f"DROP CONSTRAINT {_REJECT_PROFILE_CONSTRAINT}"
                )
            )


async def _count(engine: AsyncEngine, table: str) -> int:
    """1テーブルの行数を数える。"""
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one()
        )


async def _audit_actors(engine: AsyncEngine) -> list[tuple[object, object]]:
    """監査行の本人とアカウントを読む。

    件数だけでは「誰の操作として残ったか」が分からない。監査行は
    ``user_accounts`` への複合外部キーを持つので、Actor と食い違った値が
    書かれれば保存自体が失敗するはずだが、それはDBが守っている事実であって
    このAPIが守っている事実ではない。突き合わせはここで行う。
    """
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT person_id, account_id FROM operation_audits")
            )
        ).all()
    return [(row[0], row[1]) for row in rows]


async def _version(engine: AsyncEngine, table: str, row_id: object) -> int:
    """行の世代を読む。巻き戻ったのに世代だけ進む形の失敗を捕らえる。"""
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(
                    text(f"SELECT version FROM {table} WHERE id = :id"), {"id": row_id}
                )
            ).scalar_one()
        )


@pytest.mark.asyncio
async def test_HTTP経由の調剤完了が_調剤と処方箋を同じ要求で確定する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-01: 終了区分なら、調剤の完了と処方箋の調剤済が両方残る。"""
    # Arrange
    fixture = await setup_clinical(engine, session_factory)

    # Act
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/dispensings/{fixture.process.id.value}/completion",
            json={"completion_type": "completed"},
        )

    # Assert
    assert response.status_code == 200, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_process = await repositories.dispensing.get(
            corporate_id=fixture.corporate_id, dispensing_id=fixture.process.id
        )
        stored_prescription = await repositories.prescription.get(
            corporate_id=fixture.corporate_id, prescription_id=fixture.prescription.id
        )
    assert stored_process is not None
    assert stored_process.status is DispensingProcessStatus.COMPLETED
    assert stored_prescription is not None
    assert stored_prescription.status is PrescriptionStatus.DISPENSED
    # 監査も同じトランザクションにある。書けなければ更新ごと成立しない。
    # 調剤と処方箋の2集約を書くので2件。件数で固定すると、片方の追記が
    # 止まったときに気づける。
    expected_actor = (fixture.person.id.value, fixture.account.id.value)
    assert await _audit_actors(engine) == [expected_actor, expected_actor]


@pytest.mark.asyncio
async def test_HTTP経由でも_継続区分なら処方箋は調剤済にならない(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-02: 途中で処方箋を閉じると、リフィルの残りが調剤できなくなる。"""
    # Arrange
    fixture = await setup_clinical(engine, session_factory)

    # Act
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/dispensings/{fixture.process.id.value}/completion",
            json={
                "completion_type": "continues",
                "next_dispensing_date": "2026-09-21",
            },
        )

    # Assert
    assert response.status_code == 200, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_process = await repositories.dispensing.get(
            corporate_id=fixture.corporate_id, dispensing_id=fixture.process.id
        )
        stored_prescription = await repositories.prescription.get(
            corporate_id=fixture.corporate_id, prescription_id=fixture.prescription.id
        )
    assert stored_process is not None
    assert stored_process.status is DispensingProcessStatus.COMPLETED
    # 次回予定日が本文からドメインへ渡っている。
    assert stored_process.next_dispensing_date is not None
    assert stored_process.next_dispensing_date.value == date(2026, 9, 21)
    assert stored_prescription is not None
    assert stored_prescription.status is not PrescriptionStatus.DISPENSED


@pytest.mark.asyncio
async def test_HTTP経由の調剤完了で処方箋が無ければ_調剤の保存も巻き戻る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-03: 順序で妥協していた頃は、調剤だけが完了して処方箋が取り残された。"""
    # Arrange: 処方箋を保存しないので、調剤の保存の後に必ず失敗する
    fixture = await setup_clinical(engine, session_factory, with_prescription=False)

    # Act
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/dispensings/{fixture.process.id.value}/completion",
            json={"completion_type": "completed"},
        )

    # Assert
    assert response.status_code == 404, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        stored_process = await PostgresRepositorySet.create(work).dispensing.get(
            corporate_id=fixture.corporate_id, dispensing_id=fixture.process.id
        )
    assert stored_process is not None
    assert stored_process.status is DispensingProcessStatus.VERIFIED
    assert await _version(engine, "dispensing_processes", fixture.process.id.value) == 1
    assert await _count(engine, "operation_audits") == 0


@pytest.mark.asyncio
async def test_HTTP経由の薬歴確定が_薬歴と頭書きを同じ要求で確定する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-04: 確定と投影が同じ要求で残る。頭書きは薬歴からの投影である。"""
    # Arrange
    fixture = await setup_clinical(engine, session_factory)

    # Act
    async with _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/medication-histories/{fixture.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )

    # Assert
    assert response.status_code == 200, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        stored_record = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.record.patient_id
        )
    assert stored_record is not None
    assert stored_record.status is MedicationHistoryStatus.FINALIZED
    assert profile is not None
    assert len(profile.allergies) == 1
    assert profile.allergies[0].provenance.source_record_id == fixture.record.id
    # 薬歴と頭書きの2集約を書くので2件。
    expected_actor = (fixture.person.id.value, fixture.account.id.value)
    assert await _audit_actors(engine) == [expected_actor, expected_actor]


@pytest.mark.asyncio
async def test_HTTP経由の薬歴確定で頭書きが保存できなければ_確定も巻き戻る(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """TC-05/TC-06: 投影が失敗したら確定ごと巻き戻し、注入は必ず後始末する。"""
    # Arrange
    fixture = await setup_clinical(engine, session_factory)

    # Act
    async with reject_profile_writes(engine), _client(fixture) as client:
        response = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/medication-histories/{fixture.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )

    # Assert: 翻訳表に無い IntegrityError なので 500。薬歴は下書きのまま。
    assert response.status_code == 500, response.text
    async with PostgresUnitOfWork(session_factory) as work:
        stored_record = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
    assert stored_record is not None
    assert stored_record.status is MedicationHistoryStatus.DRAFT
    assert (
        await _version(engine, "medication_history_records", fixture.record.id.value)
        == 1
    )
    assert await _count(engine, "patient_medical_profiles") == 0
    assert await _count(engine, "operation_audits") == 0

    # TC-06: 注入を残すと、以後の結合テストが全部落ちる。
    async with engine.connect() as connection:
        remaining = (
            await connection.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = :name"),
                {"name": _REJECT_PROFILE_CONSTRAINT},
            )
        ).scalar_one()
    assert int(remaining) == 0

    # TC-07: 注入を外すと同じ要求が通る。
    #
    # これが無いと、上の Assert は「そもそも確定まで到達していなかった」場合でも
    # 成立してしまう。再実行が成功することで、(1) 500 の原因が頭書きの保存で
    # あったこと、(2) 巻き戻しが薬歴を再確定できる状態で残したことの両方が
    # 言える。全ケースが最初からGreenになる検証では、テストが空でないことを
    # 別に示す必要がある。
    async with _client(fixture) as client:
        retried = await client.post(
            f"/corporates/{fixture.corporate_id.value}"
            f"/medication-histories/{fixture.record.id.value}/finalization",
            json={"review_result": "assessment_and_instruction_recorded"},
        )
    assert retried.status_code == 200, retried.text
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        refinalized = await repositories.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=fixture.record.id
        )
        profile = await repositories.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.record.patient_id
        )
    assert refinalized is not None
    assert refinalized.status is MedicationHistoryStatus.FINALIZED
    assert profile is not None
    assert len(profile.allergies) == 1
