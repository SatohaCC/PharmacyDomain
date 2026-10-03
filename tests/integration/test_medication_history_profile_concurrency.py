"""薬歴確定・事実訂正・頭書き再構築の並行実行・排他制御・原子性のPostgreSQL結合テスト。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.correct_medication_history_fact import (
    CorrectMedicationHistoryFactCommand,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_patient_medical_profile import (
    RebuildPatientMedicalProfileCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreId
from app.infrastructure.di.bundles.clinical import (
    build_medication_history_use_cases,
)
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization import PostgresOrganizationLock
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    create_adverse_reaction_intent,
    create_allergy_intent,
    create_record,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_clock import FakeClock
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.test_clinical_transaction_http import (
    _count,
    _version,
    reject_profile_writes,
)
from tests.integration.test_identity_persistence import _person

_PHARMACIST_SUBJECT = "issuer/integration-concurrency-pharmacist"
_TEST_NOW = datetime(2026, 9, 20, 3, tzinfo=UTC)


class HookedPostgresOrganizationLock(PostgresOrganizationLock):
    """ロック取得前後に非同期フックを挟むテスト用PostgresOrganizationLock。"""

    def __init__(
        self,
        unit_of_work: PostgresUnitOfWork,
        *,
        on_before_acquire: Callable[[str], Awaitable[None]] | None = None,
        on_after_acquire: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(unit_of_work)
        self._on_before_acquire = on_before_acquire
        self._on_after_acquire = on_after_acquire

    async def acquire(self, key: str) -> None:
        if self._on_before_acquire is not None:
            await self._on_before_acquire(key)
        await super().acquire(key)
        if self._on_after_acquire is not None:
            await self._on_after_acquire(key)


@dataclass(frozen=True, slots=True)
class ConcurrencyFixture:
    """並行テスト用の前提環境一式。"""

    corporate_id: CorporateId
    store_a_id: StoreId
    store_b_id: StoreId
    patient_id: PatientId
    pharmacist_id: StaffId
    person_id: AccountPersonId
    account_id: UserAccountId
    membership_id: CorporateMembershipId
    actor: ResolvedActorContext
    authorization: AuthorizationService
    root: PostgresCompositionRoot
    clock: Clock


async def setup_concurrency_fixture(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    clock: Clock | None = None,
) -> ConcurrencyFixture:
    """法人・2店舗・患者・薬剤師スタッフ（法人管理者・店舗操作者兼任）をセットアップする。"""
    actual_clock = FakeClock(_TEST_NOW) if clock is None else clock
    corporate = create_corporate("並行制御検証薬局")
    store_a = create_store(corporate_id=corporate.id, name="サンプル薬局A")
    store_b = create_store(corporate_id=corporate.id, name="サンプル薬局B")
    patient_id = PatientId.generate()
    patient = replace(
        create_patient(corporate_id=corporate.id),
        id=patient_id,
    )
    person = _person()
    account = UserAccount(
        id=UserAccountId.generate(),
        person_id=person.id,
        external_subject=ExternalSubjectKey(_PHARMACIST_SUBJECT),
    )
    pharmacist = replace(
        create_staff(corporate_id=corporate.id),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store_a.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_b.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.CORPORATE_ADMIN,
        store_ids=frozenset({store_a.id, store_b.id}),
        staff_id=pharmacist.id,
    )
    actor = ResolvedActorContext(
        principal_id=_PHARMACIST_SUBJECT,
        roles=frozenset({ActorRole.CORPORATE_ADMIN, ActorRole.STORE_OPERATOR}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate.id,
        staff_id=pharmacist.id,
        store_ids=frozenset({store_a.id, store_b.id}),
    )
    authorization = AuthorizationService(actor)

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store_a)
        await repos.store.save(store_b)
        await repos.patient.save(patient)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(pharmacist)
        await repos.staff_person_link.save(
            StaffPersonLink(
                id=pharmacist.id,
                corporate_id=corporate.id,
                person_id=person.id,
            )
        )
        await repos.membership.save(membership)
        await work.commit()

    root = PostgresCompositionRoot(engine, session_factory, actual_clock)
    return ConcurrencyFixture(
        corporate_id=corporate.id,
        store_a_id=store_a.id,
        store_b_id=store_b.id,
        patient_id=patient_id,
        pharmacist_id=pharmacist.id,
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        actor=actor,
        authorization=authorization,
        root=root,
        clock=actual_clock,
    )


# -----------------------------------------------------------------------------
# 1. 実PostgreSQLで競合を再現する（非保護時の事実欠落の証明）
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_非保護下の再構築と確定の交錯で確定済み事実が欠落することを再現する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """患者ロックのない再構築が、確定済みの最新頭書きを上書きして消去する不具合を再現する。

    同期制御:
    1. 再構築が先行して薬歴一覧を読み込む（Record 1のみ）。
    2. 確定がRecord 2（アスピリン）を確定・頭書き反映してコミット。
    3. 再構築が古い投影元から頭書きを保存・コミット。
    4. コミット済みのアスピリンが頭書きから欠落することを確認。
    """
    fixture = await setup_concurrency_fixture(engine, session_factory)

    # Record 1: 確定済み（ペニシリン）
    record1 = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )
    # Record 2: 未確定下書き（アスピリン）
    draft2 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="アスピリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record1)
        await save_history_with_event(repos, draft2)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record1,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    rebuild_read_done = asyncio.Event()
    finalize_committed = asyncio.Event()

    # タスク1: 非保護の手動再構築（ロックを取らずに古い記録を読んでから待機）
    async def unprotected_rebuild() -> None:
        async with PostgresUnitOfWork(session_factory) as work:
            repos = PostgresRepositorySet.create(work)
            # Record 2 がまだ未確定の時点で投影元を取得
            all_records = await repos.medication_history.list_for_profile_projection(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
            )
            records = tuple(r for r in all_records if r.is_projection_eligible)
            assert len(records) == 1
            rebuild_read_done.set()

            # 確定処理のコミットを待つ
            await finalize_committed.wait()

            # 古い取得結果に基づいて頭書きを作り直し、上書き保存
            existing = await repos.patient_medical_profile.get_by_patient(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
            )
            assert existing is not None
            stale_profile = PatientMedicalProfile.rebuild_from(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
                records=tuple(r for r in records if r.is_projection_eligible),
            )
            await repos.patient_medical_profile.save(
                replace(stale_profile, id=existing.id)
            )
            await work.commit()

    # タスク2: 薬歴2の確定処理
    async def do_finalize() -> None:
        await rebuild_read_done.wait()
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.medication_history.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(draft2.id.value),
                    review_result="assessment_and_instruction_recorded",
                )
            )
        finalize_committed.set()

    await asyncio.gather(unprotected_rebuild(), do_finalize())

    # 検証: 非保護下では、確定されたアスピリンが頭書きから消えている
    async with PostgresUnitOfWork(session_factory) as work:
        stored_profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
    assert stored_profile is not None
    allergen_names = [a.allergen.value for a in stored_profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" not in allergen_names, (
        "非保護の再構築によってアスピリンが上書き消失したこと"
    )


@pytest.mark.asyncio
async def test_非保護下の再構築と事実訂正の交錯で訂正事実が欠落することを再現する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """患者ロックのない再構築が、事実訂正後の最新頭書きを上書きして消去する不具合を再現する。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    rebuild_read_done = asyncio.Event()
    correction_committed = asyncio.Event()

    async def unprotected_rebuild() -> None:
        async with PostgresUnitOfWork(session_factory) as work:
            repos = PostgresRepositorySet.create(work)
            all_records = await repos.medication_history.list_for_profile_projection(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
            )
            records = tuple(r for r in all_records if r.is_projection_eligible)
            assert len(records) == 1
            rebuild_read_done.set()

            await correction_committed.wait()

            existing = await repos.patient_medical_profile.get_by_patient(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
            )
            assert existing is not None
            stale_profile = PatientMedicalProfile.rebuild_from(
                corporate_id=fixture.corporate_id,
                patient_id=fixture.patient_id,
                records=tuple(r for r in records if r.is_projection_eligible),
            )
            await repos.patient_medical_profile.save(
                replace(stale_profile, id=existing.id)
            )
            await work.commit()

    async def do_correct() -> None:
        await rebuild_read_done.wait()
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.medication_history.correct_fact.execute(
                CorrectMedicationHistoryFactCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(record.id.value),
                    target="profile_updates.new_allergies",
                    operation="append",
                    value={
                        "allergen": "アスピリン",
                        "reaction": "発疹",
                        "severity": "moderate",
                    },
                    reason="アレルギー情報の訂正追加",
                )
            )
        correction_committed.set()

    await asyncio.gather(unprotected_rebuild(), do_correct())

    async with PostgresUnitOfWork(session_factory) as work:
        stored_profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
    assert stored_profile is not None
    allergen_names = [a.allergen.value for a in stored_profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" not in allergen_names, (
        "非保護の再構築によって訂正アレルゲンが消失したこと"
    )


# -----------------------------------------------------------------------------
# 2. ロック取得順序の統一と双方の先行順序（保護下の並行実行）
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_保護下の再構築先行_確定が待機後に最新頭書きを反映する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """手動再構築が先に患者ロックを取り、待機した確定がロック解放後に最新頭書きを反映する。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    record1 = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )
    draft2 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="アスピリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record1)
        await save_history_with_event(repos, draft2)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record1,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    rebuild_lock_acquired = asyncio.Event()
    finalize_attempting_lock = asyncio.Event()

    async def do_rebuild() -> None:
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_rebuild_locked(key: str) -> None:
                rebuild_lock_acquired.set()
                await finalize_attempting_lock.wait()

            lock = HookedPostgresOrganizationLock(
                work, on_after_acquire=on_rebuild_locked
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.rebuild_medical_profile.execute(
                RebuildPatientMedicalProfileCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    patient_id=str(fixture.patient_id.value),
                    as_of=fixture.clock.now().date(),
                )
            )
            await work.commit()

    async def do_finalize() -> None:
        await rebuild_lock_acquired.wait()
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_finalize_before_lock(key: str) -> None:
                finalize_attempting_lock.set()

            lock = HookedPostgresOrganizationLock(
                work, on_before_acquire=on_finalize_before_lock
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(draft2.id.value),
                    review_result="assessment_and_instruction_recorded",
                )
            )
            await work.commit()

    await asyncio.gather(do_rebuild(), do_finalize())

    # 検証: ロック待機後に確定が再投影を実行したため、両方の事実が残る
    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
    assert profile is not None
    allergen_names = [a.allergen.value for a in profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" in allergen_names


@pytest.mark.asyncio
async def test_保護下の確定先行_再構築が待機後に最新確定事実を含めて再構築する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """確定が先に患者ロックを取り、待機した手動再構築が最新の確定結果を含めて反映する。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    record1 = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )
    draft2 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="アスピリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record1)
        await save_history_with_event(repos, draft2)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record1,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    finalize_lock_acquired = asyncio.Event()
    rebuild_attempting_lock = asyncio.Event()

    async def do_finalize() -> None:
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_finalize_locked(key: str) -> None:
                finalize_lock_acquired.set()
                await rebuild_attempting_lock.wait()

            lock = HookedPostgresOrganizationLock(
                work, on_after_acquire=on_finalize_locked
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(draft2.id.value),
                    review_result="assessment_and_instruction_recorded",
                )
            )
            await work.commit()

    async def do_rebuild() -> None:
        await finalize_lock_acquired.wait()
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_rebuild_before_lock(key: str) -> None:
                rebuild_attempting_lock.set()

            lock = HookedPostgresOrganizationLock(
                work, on_before_acquire=on_rebuild_before_lock
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.rebuild_medical_profile.execute(
                RebuildPatientMedicalProfileCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    patient_id=str(fixture.patient_id.value),
                    as_of=fixture.clock.now().date(),
                )
            )
            await work.commit()

    await asyncio.gather(do_finalize(), do_rebuild())

    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
    assert profile is not None
    allergen_names = [a.allergen.value for a in profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" in allergen_names


@pytest.mark.asyncio
async def test_保護下の事実訂正と再構築の交錯_訂正事実が失われずに頭書きに反映される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """事実訂正と手動再構築が並行実行されても、患者ロックにより訂正事実が正しく維持される。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    correct_lock_acquired = asyncio.Event()
    rebuild_attempting_lock = asyncio.Event()

    async def do_correct() -> None:
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_correct_locked(key: str) -> None:
                correct_lock_acquired.set()
                await rebuild_attempting_lock.wait()

            lock = HookedPostgresOrganizationLock(
                work, on_after_acquire=on_correct_locked
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.correct_fact.execute(
                CorrectMedicationHistoryFactCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(record.id.value),
                    target="profile_updates.new_allergies",
                    operation="append",
                    value={
                        "allergen": "アスピリン",
                        "reaction": "発疹",
                        "severity": "moderate",
                    },
                    reason="アレルゲン追加",
                )
            )
            await work.commit()

    async def do_rebuild() -> None:
        await correct_lock_acquired.wait()
        async with PostgresUnitOfWork(session_factory) as work:

            async def on_rebuild_before_lock(key: str) -> None:
                rebuild_attempting_lock.set()

            lock = HookedPostgresOrganizationLock(
                work, on_before_acquire=on_rebuild_before_lock
            )
            use_cases = build_medication_history_use_cases(
                repositories=PostgresRepositorySet.create(work),
                corporate_access=CorporateAccessService(
                    PostgresRepositorySet.create(work).corporate,
                    fixture.authorization,
                ),
                clock=fixture.clock,
                unit_of_work=work,
                organization_lock=lock,
            )
            await use_cases.rebuild_medical_profile.execute(
                RebuildPatientMedicalProfileCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    patient_id=str(fixture.patient_id.value),
                    as_of=fixture.clock.now().date(),
                )
            )
            await work.commit()

    await asyncio.gather(do_correct(), do_rebuild())

    async with PostgresUnitOfWork(session_factory) as work:
        profile = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
    assert profile is not None
    allergen_names = [a.allergen.value for a in profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" in allergen_names


# -----------------------------------------------------------------------------
# 3. 初回投影の競合（単一頭書きへの収束と一意制約保護）
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_初回投影の並行確定_一意制約違反にならず単一頭書きに収束する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """頭書きがまだ存在しない初期状態で2件の確定が並行実行されても、重複キーにならず1件の頭書きへ収束する。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    draft1 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=20),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
        ),
    )
    draft2 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_b_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="アスピリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, draft1)
        await save_history_with_event(repos, draft2)
        await work.commit()

    # DB上に頭書きが存在しないことを確認
    assert await _count(engine, "patient_medical_profiles") == 0

    barrier = asyncio.Barrier(2)

    async def finalize_task(record_id: MedicationHistoryRecordId) -> None:
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await barrier.wait()
            await scope.use_cases.medication_history.finalize.execute(
                FinalizeMedicationHistoryCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    record_id=str(record_id.value),
                    review_result="assessment_and_instruction_recorded",
                )
            )

    await asyncio.gather(finalize_task(draft1.id), finalize_task(draft2.id))

    # 検証: 1行のみ作成され、両方の事実が集約されている
    assert await _count(engine, "patient_medical_profiles") == 1
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        profile = await repos.patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
        )
        rec1 = await repos.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=draft1.id
        )
        rec2 = await repos.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=draft2.id
        )
    assert profile is not None
    assert rec1 is not None and rec1.is_finalized
    assert rec2 is not None and rec2.is_finalized
    allergen_names = [a.allergen.value for a in profile.allergies]
    assert "ペニシリン" in allergen_names
    assert "アスピリン" in allergen_names


# -----------------------------------------------------------------------------
# 4. 保存失敗時のロールバック（原子性の保証）
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_頭書き保存失敗時は薬歴確定もロールバックされる(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """頭書き保存が制約違反で失敗した場合、薬歴の確定状態もDBへ残らずロールバックされる。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, draft)
        await work.commit()

    version_before = await _version(
        engine, "medication_history_records", draft.id.value
    )
    audit_count_before = await _count(engine, "operation_audits")

    # 頭書きテーブルへ書き込み拒否制約を一時的に注入
    async with reject_profile_writes(engine):
        with pytest.raises(IntegrityError):
            async with fixture.root.request_scope(
                authorization=fixture.authorization
            ) as scope:
                await scope.use_cases.medication_history.finalize.execute(
                    FinalizeMedicationHistoryCommand(
                        corporate_id=str(fixture.corporate_id.value),
                        record_id=str(draft.id.value),
                        review_result="assessment_and_instruction_recorded",
                    )
                )

    # 薬歴は下書きのまま、バージョンも監査も増えていない
    async with PostgresUnitOfWork(session_factory) as work:
        stored = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id, record_id=draft.id
        )
    assert stored is not None
    assert stored.status is MedicationHistoryStatus.DRAFT
    assert (
        await _version(engine, "medication_history_records", draft.id.value)
        == version_before
    )
    assert await _count(engine, "patient_medical_profiles") == 0
    assert await _count(engine, "operation_audits") == audit_count_before


@pytest.mark.asyncio
async def test_頭書き保存失敗時は事実訂正もロールバックされる(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """頭書き保存が失敗した場合、事実訂正も薬歴へ反映されずロールバックされる。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=10),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record)
        initial_profile = PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record,),
        )
        await repos.patient_medical_profile.save(initial_profile)
        await work.commit()

    version_before = await _version(
        engine, "medication_history_records", record.id.value
    )

    async with reject_profile_writes(engine):
        with pytest.raises(IntegrityError):
            async with fixture.root.request_scope(
                authorization=fixture.authorization
            ) as scope:
                await scope.use_cases.medication_history.correct_fact.execute(
                    CorrectMedicationHistoryFactCommand(
                        corporate_id=str(fixture.corporate_id.value),
                        record_id=str(record.id.value),
                        target="method",
                        operation="replace",
                        value="online",
                        reason="訂正テスト",
                    )
                )

    async with PostgresUnitOfWork(session_factory) as work:
        stored = await PostgresRepositorySet.create(work).medication_history.get(
            corporate_id=fixture.corporate_id, record_id=record.id
        )
    assert stored is not None
    assert stored.fact_corrections == ()
    assert (
        await _version(engine, "medication_history_records", record.id.value)
        == version_before
    )


# -----------------------------------------------------------------------------
# 5. 既存契約の検証（複数店舗、ID維持、保存期限延伸）
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_複数店舗の記録が頭書きへ集約され未確定は除外される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """店舗A・店舗Bの確定記録が集約され、未確定の下書きは頭書きへ投影されない。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    # 店舗Aの確定記録（ペニシリン）
    record_a = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_a_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=40),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )
    # 店舗Bの未確定下書き（除外されるべきアレルゲン）
    draft_b = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_b_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=20),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="除外されるべき下書き"),)
        ),
    )
    # 店舗Bの確定記録（副作用）
    record_b = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_b_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now() - timedelta(minutes=10),
            profile_updates=ProfileUpdateIntents(
                new_adverse_reactions=(
                    create_adverse_reaction_intent(medicine_name="ロキソプロフェン"),
                )
            ),
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, record_a)
        await save_history_with_event(repos, draft_b)
        await save_history_with_event(repos, record_b)
        await work.commit()

    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        dto = await scope.use_cases.medication_history.rebuild_medical_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=fixture.clock.now().date(),
            )
        )

    assert len(dto.allergies) == 1
    assert dto.allergies[0].allergen == "ペニシリン"
    assert len(dto.adverse_reactions) == 1
    assert dto.adverse_reactions[0].medicine_name == "ロキソプロフェン"
    assert "除外されるべき下書き" not in [a.allergen for a in dto.allergies]


@pytest.mark.asyncio
async def test_再構築と確定を繰り返しても頭書きIDが維持される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """初回確定、2回目確定、手動再構築、事実訂正を経ても同一の頭書きIDが維持される。"""
    fixture = await setup_concurrency_fixture(engine, session_factory)

    draft1 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=30),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
        ),
    )
    draft2 = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_a_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=15),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="アスピリン"),)
        ),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, draft1)
        await save_history_with_event(repos, draft2)
        await work.commit()

    # 1. 薬歴1を確定（頭書き初回作成）
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.medication_history.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(draft1.id.value),
                review_result="assessment_and_instruction_recorded",
            )
        )
    async with PostgresUnitOfWork(session_factory) as work:
        p1 = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
        )
    assert p1 is not None

    # 2. 薬歴2を確定（頭書き更新）
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.medication_history.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(draft2.id.value),
                review_result="assessment_and_instruction_recorded",
            )
        )
    async with PostgresUnitOfWork(session_factory) as work:
        p2 = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
        )
    assert p2 is not None
    assert p2.id == p1.id

    # 3. 手動再構築
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.medication_history.rebuild_medical_profile.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=fixture.clock.now().date(),
            )
        )
    async with PostgresUnitOfWork(session_factory) as work:
        p3 = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
        )
    assert p3 is not None
    assert p3.id == p1.id

    # 4. 事実訂正
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.medication_history.correct_fact.execute(
            CorrectMedicationHistoryFactCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(draft1.id.value),
                target="method",
                operation="replace",
                value="face_to_face",
                reason="確認訂正",
            )
        )
    async with PostgresUnitOfWork(session_factory) as work:
        p4 = await PostgresRepositorySet.create(
            work
        ).patient_medical_profile.get_by_patient(
            corporate_id=fixture.corporate_id, patient_id=fixture.patient_id
        )
    assert p4 is not None
    assert p4.id == p1.id


@pytest.mark.asyncio
async def test_確定時に同一患者の過去薬歴の保存期限が延伸される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """新規薬歴の確定時に、同じ患者ロック内で過去薬歴の保存期限が正しく延伸される。"""
    now = datetime(2026, 9, 20, 3, tzinfo=UTC)
    clock = FakeClock(now)
    fixture = await setup_concurrency_fixture(engine, session_factory, clock=clock)

    old_date = datetime(2024, 1, 10, 3, tzinfo=UTC)
    old_record = replace(
        finalize_record_with_review(
            create_record(
                corporate_id=fixture.corporate_id,
                store_id=fixture.store_a_id,
                patient_id=fixture.patient_id,
                counselor_id=fixture.pharmacist_id,
                counseled_at=old_date,
            ),
            finalized_at=FinalizedTimestamp(old_date),
        ),
        retention_expiry_date=date(2027, 1, 10),
    )
    new_draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_b_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=now,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await save_history_with_event(repos, old_record)
        await save_history_with_event(repos, new_draft)
        await work.commit()

    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        await scope.use_cases.medication_history.finalize.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(new_draft.id.value),
                review_result="assessment_and_instruction_recorded",
            )
        )

    # 過去薬歴も新薬歴と同じ延伸日付へ更新されている
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        stored_old = await repos.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=old_record.id
        )
        stored_new = await repos.medication_history.get(
            corporate_id=fixture.corporate_id, record_id=new_draft.id
        )
    assert stored_old is not None
    assert stored_new is not None
    assert stored_new.retention_expiry_date == date(2029, 9, 20)
    assert stored_old.retention_expiry_date == date(2029, 9, 20)
