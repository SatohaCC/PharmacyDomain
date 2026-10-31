"""Phase 5 Work Unit 5a: 資格剥奪の即時反映と権限変更×業務保存の直列化結合テスト（TC-090, TC-092）。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime
from http import HTTPStatus

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingCommand,
)
from app.bootstrap import create_app
from app.domain.dispensing.exceptions import DispensingPharmacistQualificationError
from app.domain.dispensing.primitives import (
    DispensingCompletionType,
    DispensingProcessStatus,
)
from app.domain.identity.entities import (
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
)
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryReviewResult,
)
from app.domain.patient.identifiers import PatientId
from app.domain.shared.actor import UserAccountId
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.organization_lock import PostgresOrganizationLock
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.factories.dispensing_factory import (
    complete_dispensing,
    create_dispensing,
    verify_passed,
)
from tests.factories.medication_history_factory import (
    create_record,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.test_identity_persistence import _person

_CLOCK = FakeClock(datetime(2026, 9, 20, 3, tzinfo=UTC))


# ==============================================================================
# TC-090: ログイン中の薬剤師資格削除の即時反映と過去署名履歴の保持
# ==============================================================================
@pytest.mark.asyncio
async def test_TC090_資格変更の即時反映_ログイン中に薬剤師資格を削除すると次要求と進行中保存を拒否し過去署名を保持する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    corporate = create_corporate("資格即時反映薬局")
    store = create_store(corporate_id=corporate.id)
    patient_id = PatientId.generate()
    patient = replace(create_patient(corporate_id=corporate.id), id=patient_id)
    person = _person(corporate_id=corporate.id)
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey("issuer/tc090-pharmacist"),
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

    # 1. 過去に確定済みの処方・調剤・薬歴（薬剤師本人の署名入り）と、進行中の第2処方・調剤を用意
    past_prescription = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient_id,
        document_number="DOC-TC090-PAST",
    ).ready_for_dispensing()
    past_dispensing = complete_dispensing(
        replace(
            create_dispensing(
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient_id,
                prescription_id=past_prescription.id,
            ),
            dispenser_id=pharmacist.id,
        )
    )
    past_record = finalize_record_with_review(
        replace(
            create_record(
                corporate_id=corporate.id,
                store_id=store.id,
                dispensing_id=past_dispensing.id,
                prescription_id=past_prescription.id,
                patient_id=patient_id,
                counselor_id=pharmacist.id,
                counseled_at=_CLOCK.now(),
            ),
            recorded_by=pharmacist.id,
        ),
        finalized_at=FinalizedTimestamp(_CLOCK.now()),
        finalized_by=pharmacist.id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )

    active_prescription = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient_id,
        document_number="DOC-TC090-ACTIVE",
    ).ready_for_dispensing()
    active_dispensing = verify_passed(
        replace(
            create_dispensing(
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient_id,
                prescription_id=active_prescription.id,
            ),
            dispenser_id=pharmacist.id,
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store)
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
        await repos.manager_assignment.save(
            create_manager_assignment(
                corporate_id=corporate.id,
                store_id=store.id,
                staff_id=pharmacist.id,
                person_id=person.id,
            )
        )
        await repos.prescription.save(past_prescription)
        await repos.dispensing.save(past_dispensing)
        await save_history_with_event(repos, past_record)
        await repos.prescription.save(active_prescription)
        await repos.dispensing.save(active_dispensing)
        await work.commit()

    # ログイン済みActor（トークン発行時点のスナップショット）
    actor = ResolvedActorContext(
        principal_id="issuer/tc090-pharmacist",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate.id,
        staff_id=pharmacist.id,
        store_ids=frozenset({store.id}),
    )
    provider = StubActorContextProvider(actor)
    app = create_app(actor_provider=provider)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=provider,
            composition_root=PostgresCompositionRoot(engine, session_factory, _CLOCK),
        ),
    )

    # 2. ログイン中に管理者が当該スタッフの薬剤師資格を削除してDB確定
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        loaded_staff = await repos.staff.get(
            corporate_id=corporate.id, staff_id=pharmacist.id
        )
        assert loaded_staff is not None
        await repos.staff.save(
            loaded_staff.update_qualifications(StaffQualifications.empty())
        )
        await work.commit()

    # 3. 再認証なしのまま同じトークンで進行中調剤の交付完了や薬歴追記を要求 -> 403 FORBIDDEN で拒否
    cid = str(corporate.id.value)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    ) as client:
        res_complete = await client.post(
            f"/corporates/{cid}/dispensings/{active_dispensing.id.value}/completion",
            json={"completion_type": "completed"},
        )
        assert res_complete.status_code == HTTPStatus.FORBIDDEN

        res_amend = await client.post(
            f"/corporates/{cid}/medication-histories/{past_record.id.value}/amendments",
            json={
                "reason": "資格剥奪後の追記試行",
                "amended_soap": {
                    "subjective": [{"text": "S"}],
                    "objective": [{"text": "O"}],
                    "assessment": [{"text": "A"}],
                    "plan": [{"text": "P"}],
                },
            },
        )
        assert res_amend.status_code == HTTPStatus.FORBIDDEN

    # 4. 進行中の状態が不変であり、かつ過去の確定済み調剤・薬歴の署名（dispenser_id / counselor_id / finalized_by）が消えていないことを検証
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        reloaded_active = await repos.dispensing.get(
            corporate_id=corporate.id, dispensing_id=active_dispensing.id
        )
        assert reloaded_active is not None
        assert reloaded_active.status is DispensingProcessStatus.VERIFIED

        reloaded_past_disp = await repos.dispensing.get(
            corporate_id=corporate.id, dispensing_id=past_dispensing.id
        )
        assert reloaded_past_disp is not None
        assert reloaded_past_disp.status is DispensingProcessStatus.COMPLETED
        assert reloaded_past_disp.dispenser_id == pharmacist.id

        reloaded_past_rec = await repos.medication_history.get(
            corporate_id=corporate.id, record_id=past_record.id
        )
        assert reloaded_past_rec is not None
        assert reloaded_past_rec.counselor_id == pharmacist.id
        assert reloaded_past_rec.finalized_by == pharmacist.id
        assert len(reloaded_past_rec.amendments) == 0


# ==============================================================================
# TC-092: 権限変更（店舗権限停止・資格削除）と業務保存の並行直列化
# ==============================================================================
@pytest.mark.asyncio
async def test_TC092_権限変更と業務保存の並行_停止先行なら403で保存拒否され業務先行なら完了後に権限停止される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    corporate = create_corporate("並行権限変更薬局")
    store = create_store(corporate_id=corporate.id)
    patient_id = PatientId.generate()
    patient = replace(create_patient(corporate_id=corporate.id), id=patient_id)
    person = _person(corporate_id=corporate.id)
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey("issuer/tc092-pharmacist"),
    )
    pharmacist = replace(
        create_staff(corporate_id=corporate.id),
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
        corporate_id=corporate.id,
        role=MembershipRole.STORE_OPERATOR,
        store_ids=frozenset({store.id}),
        staff_id=pharmacist.id,
    )

    prescription_1 = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient_id,
        document_number="DOC-TC092-1",
    ).ready_for_dispensing()
    dispensing_1 = verify_passed(
        replace(
            create_dispensing(
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient_id,
                prescription_id=prescription_1.id,
            ),
            dispenser_id=pharmacist.id,
        )
    )

    prescription_2 = create_prescription(
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient_id,
        document_number="DOC-TC092-2",
    ).ready_for_dispensing()
    dispensing_2 = verify_passed(
        replace(
            create_dispensing(
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient_id,
                prescription_id=prescription_2.id,
            ),
            dispenser_id=pharmacist.id,
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store)
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
        await repos.manager_assignment.save(
            create_manager_assignment(
                corporate_id=corporate.id,
                store_id=store.id,
                staff_id=pharmacist.id,
                person_id=person.id,
            )
        )
        await repos.prescription.save(prescription_1)
        await repos.dispensing.save(dispensing_1)
        await repos.prescription.save(prescription_2)
        await repos.dispensing.save(dispensing_2)
        await work.commit()

    actor = ResolvedActorContext(
        principal_id="issuer/tc092-pharmacist",
        roles=frozenset({ActorRole.STORE_OPERATOR}),
        person_id=person.id,
        account_id=account.id,
        membership_id=membership.id,
        corporate_id=corporate.id,
        staff_id=pharmacist.id,
        store_ids=frozenset({store.id}),
    )
    root = PostgresCompositionRoot(engine, session_factory, _CLOCK)

    # ------------------------------------------------------------------
    # 順序A: 業務保存が先に法人ロックを取って完了確定 → その後で権限変更が確定
    # ------------------------------------------------------------------
    order_a_events: list[str] = []
    lock_acquired_by_clinical = asyncio.Event()

    async def _clinical_first() -> None:
        async with root.request_scope(
            authorization=AuthorizationService(actor)
        ) as scope:
            await PostgresOrganizationLock(scope._unit_of_work).acquire(
                f"corporate:{corporate.id.value}"
            )
            order_a_events.append("clinical_locked")
            lock_acquired_by_clinical.set()
            await asyncio.sleep(0.05)
            await scope.use_cases.dispensing.complete.execute(
                CompleteDispensingCommand(
                    corporate_id=str(corporate.id.value),
                    dispensing_id=str(dispensing_1.id.value),
                    completion_type=DispensingCompletionType.COMPLETED.value,
                )
            )
            order_a_events.append("clinical_completed")

    async def _revoke_second() -> None:
        await lock_acquired_by_clinical.wait()
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresOrganizationLock(work).acquire(
                f"corporate:{corporate.id.value}"
            )
            order_a_events.append("revoke_locked_after_clinical")

    await asyncio.gather(_clinical_first(), _revoke_second())
    assert order_a_events == [
        "clinical_locked",
        "clinical_completed",
        "revoke_locked_after_clinical",
    ]

    # ------------------------------------------------------------------
    # 順序B: 権限停止（店舗権限停止）が先に法人ロックを取って確定 → 待機していた業務保存は Guard 再検証で拒否
    # ------------------------------------------------------------------
    lock_acquired_by_revoke = asyncio.Event()

    async def _revoke_first() -> None:
        async with PostgresUnitOfWork(session_factory) as work:
            await PostgresOrganizationLock(work).acquire(
                f"corporate:{corporate.id.value}"
            )
            lock_acquired_by_revoke.set()
            await asyncio.sleep(0.05)
            repos = PostgresRepositorySet.create(work)
            loaded_mem = await repos.membership.get(membership.id)
            assert loaded_mem is not None
            await repos.membership.save(
                replace(loaded_mem, status=AccountStatus.SUSPENDED)
            )
            await work.commit()

    async def _clinical_second() -> None:
        await lock_acquired_by_revoke.wait()
        with pytest.raises(
            (AuthorizationError, DispensingPharmacistQualificationError)
        ):
            async with root.request_scope(
                authorization=AuthorizationService(actor)
            ) as scope:
                await scope.use_cases.dispensing.complete.execute(
                    CompleteDispensingCommand(
                        corporate_id=str(corporate.id.value),
                        dispensing_id=str(dispensing_2.id.value),
                        completion_type=DispensingCompletionType.COMPLETED.value,
                    )
                )

    await asyncio.gather(_revoke_first(), _clinical_second())

    # Assert: dispensing_1 は完了済みとして保持、dispensing_2 は未完了（VERIFIED）のままロールバックされている
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        d1 = await repos.dispensing.get(
            corporate_id=corporate.id, dispensing_id=dispensing_1.id
        )
        d2 = await repos.dispensing.get(
            corporate_id=corporate.id, dispensing_id=dispensing_2.id
        )
        assert d1 is not None and d1.status is DispensingProcessStatus.COMPLETED
        assert d2 is not None and d2.status is DispensingProcessStatus.VERIFIED
