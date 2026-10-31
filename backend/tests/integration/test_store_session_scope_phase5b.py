"""Phase 5b: 店舗セッション・取得/更新範囲の結合・HTTPテスト (TC-094〜TC-102)。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.bootstrap import create_app
from app.domain.care_event.entities import Event
from app.domain.care_event.identifiers import EventId, EventTypeId
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
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
from app.domain.medication_history.identifiers import ExternalCorrectionId
from app.domain.medication_history.primitives import (
    CorrectionDocumentNumber,
    ExternalCorrectionKind,
    ExternalCorrectionReason,
    ExternalCorrectionTimestamp,
)
from app.domain.medication_history.value_objects import ExternalPrescriptionCorrection
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreStatus
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
    PostgresLocalAuthentication,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.presentational.authentication import UnconfiguredActorContextProvider
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import (
    create_record,
    finalize_record_with_review,
)
from tests.factories.persistence_factory import create_coverage, create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_manager_assignment, create_store
from tests.fakes.fake_clock import FakeClock
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.medication_history_helpers import save_history_event

_NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
_TODAY = date(2026, 10, 29)
_PASSWORD = "ValidPassword!12345"


def _person(corporate_id: CorporateId, last_name: str = "店舗") -> AccountPerson:
    return AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart(last_name),
                first_name=PersonNamePart("太郎"),
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("テンポ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
    )


def _local_auth_app(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    clock: FakeClock,
) -> FastAPI:
    app = create_app(local_authentication_enabled=True)
    setattr(
        app.state,
        STATE_ATTRIBUTE,
        PresentationState(
            actor_provider=UnconfiguredActorContextProvider(),
            composition_root=PostgresCompositionRoot(engine, session_factory, clock),
            local_authentication=PostgresLocalAuthentication(session_factory, clock),
        ),
    )
    return app


async def _login_Ready(
    session_factory: async_sessionmaker[AsyncSession],
    clock: FakeClock,
    *,
    corporate_id: CorporateId,
    email: str,
    subject: str,
) -> str:
    """初期パスワードを発行して初回変更まで済ませ、未選択状態の通常トークンを返す。"""
    auth = PostgresLocalAuthentication(session_factory, clock)
    async with PostgresUnitOfWork(session_factory) as work:
        writer = PostgresCredentialWriter(work)
        await writer.issue(corporate_id, email, "InitialPassword!123", subject)
        await work.commit()
    initial = await auth.login(str(corporate_id.value), email, "InitialPassword!123")
    changed = await auth.change_password(initial.access_token, _PASSWORD)
    return changed.access_token


@pytest.mark.asyncio
async def test_TC094_選択可能店舗一覧がMembership許可店舗と当日Staff所属と有効店舗の積集合だけを返す(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(_NOW)
    corporate = create_corporate(name="TC094法人")
    other_corporate = create_corporate(name="TC094別法人")

    # A1: 主所属（当日有効）・許可・有効店舗 -> 返る
    store_a1 = create_store(corporate_id=corporate.id, name="A1主所属店", code="A01")
    # A2: 兼務（当日が開始日境界）・許可・有効店舗 -> 返る
    store_a2 = create_store(
        corporate_id=corporate.id, name="A2兼務開始日店", code="A02"
    )
    # A3: 兼務（当日が終了日境界）・許可・有効店舗 -> 返る
    store_a3 = create_store(
        corporate_id=corporate.id, name="A3兼務終了日店", code="A03"
    )
    # A4: 兼務（明日開始＝開始前）・許可・有効店舗 -> 返らない
    store_a4 = create_store(corporate_id=corporate.id, name="A4開始前店", code="A04")
    # A5: 兼務（昨日終了＝終了翌日）・許可・有効店舗 -> 返らない
    store_a5 = create_store(corporate_id=corporate.id, name="A5終了翌日店", code="A05")
    # A6: 兼務（当日有効）だが Membership で店舗別停止中 -> 返らない
    store_a6 = create_store(corporate_id=corporate.id, name="A6権限停止店", code="A06")
    # A7: 兼務（当日有効）・許可だが 店舗自体が休止中 -> 返らない
    store_a7 = replace(
        create_store(corporate_id=corporate.id, name="A7休止店", code="A07"),
        status=StoreStatus.SUSPENDED,
    )
    # A8: 当日有効な兼務があるが Membership 許可に含まれない -> 返らない
    store_a8 = create_store(corporate_id=corporate.id, name="A8非許可店", code="A08")
    # A9: Membership 許可にあるが Staff 所属がない -> 返らない
    store_a9 = create_store(corporate_id=corporate.id, name="A9未所属店", code="A09")
    # B1: 他法人店舗 -> 返らない
    store_b1 = create_store(
        corporate_id=other_corporate.id, name="B1他法人店", code="B01"
    )

    person = _person(corporate.id)
    subject = "local:tc094-user"
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(subject),
    )
    staff = replace(
        create_staff(corporate_id=corporate.id, code="ST094"),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_a2.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=_TODAY),
            ),
            StoreAffiliation(
                store_id=store_a3.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1), end_date=_TODAY),
            ),
            StoreAffiliation(
                store_id=store_a4.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 10, 30)),
            ),
            StoreAffiliation(
                store_id=store_a5.id,
                is_primary=False,
                period=AffiliationPeriod(
                    start_date=date(2026, 1, 1), end_date=date(2026, 10, 28)
                ),
            ),
            StoreAffiliation(
                store_id=store_a6.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_a7.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_a8.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(id=staff.id, corporate_id=corporate.id, person_id=person.id)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.STORE_OPERATOR,
        staff_id=staff.id,
        store_ids=frozenset(
            {
                store_a1.id,
                store_a2.id,
                store_a3.id,
                store_a4.id,
                store_a5.id,
                store_a6.id,
                store_a7.id,
                store_a9.id,
            }
        ),
        suspended_store_ids=frozenset({store_a6.id}),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.corporate.save(other_corporate)
        for st in (
            store_a1,
            store_a2,
            store_a3,
            store_a4,
            store_a5,
            store_a6,
            store_a7,
            store_a8,
            store_a9,
            store_b1,
        ):
            await repos.store.save(st)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.membership.save(membership)
        await work.commit()

    token = await _login_Ready(
        session_factory,
        clock,
        corporate_id=corporate.id,
        email="tc094@example.com",
        subject=subject,
    )
    app = _local_auth_app(engine, session_factory, clock)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.get("/me/stores")

    assert resp.status_code == 200, resp.text
    rows = resp.json()
    returned_ids = {item["id"] for item in rows}
    expected_ids = {
        str(store_a1.id.value),
        str(store_a2.id.value),
        str(store_a3.id.value),
    }
    assert returned_ids == expected_ids
    # 他店舗の名称やコードが一切含まれないことを確認
    body_text = resp.text
    for hidden_name in (
        "A4開始前店",
        "A5終了翌日店",
        "A6権限停止店",
        "A7休止店",
        "A8非許可店",
        "A9未所属店",
        "B1他法人店",
    ):
        assert hidden_name not in body_text


@pytest.mark.asyncio
async def test_TC095_TC097_TC107_店舗コンテキスト選択と別タブ独立トークンおよび改ざん拒否(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(_NOW)
    corporate = create_corporate(name="TC095法人")
    other_corporate = create_corporate(name="TC095別法人")
    store_a1 = create_store(corporate_id=corporate.id, name="A1店舗", code="A01")
    store_a2 = create_store(corporate_id=corporate.id, name="A2店舗", code="A02")
    store_a3_unpermitted = create_store(
        corporate_id=corporate.id, name="A3非許可店舗", code="A03"
    )
    store_b1 = create_store(
        corporate_id=other_corporate.id, name="B1他法人店舗", code="B01"
    )

    person = _person(corporate.id)
    subject = "local:tc095-user"
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(subject),
    )
    staff = replace(
        create_staff(corporate_id=corporate.id, code="ST095"),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_a2.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(id=staff.id, corporate_id=corporate.id, person_id=person.id)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.STORE_OPERATOR,
        staff_id=staff.id,
        store_ids=frozenset({store_a1.id, store_a2.id}),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.corporate.save(other_corporate)
        for st in (store_a1, store_a2, store_a3_unpermitted, store_b1):
            await repos.store.save(st)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.membership.save(membership)
        await work.commit()

    base_token = await _login_Ready(
        session_factory,
        clock,
        corporate_id=corporate.id,
        email="tc095@example.com",
        subject=subject,
    )
    app = _local_auth_app(engine, session_factory, clock)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        # 初期ログイン直後は selected_store_id が None
        me_initial = await client.get(
            "/me", headers={"Authorization": f"Bearer {base_token}"}
        )
        assert me_initial.status_code == 200
        assert me_initial.json()["selected_store_id"] is None

        # TC-095: A1 を選択
        select_a1 = await client.post(
            "/auth/store-context",
            headers={"Authorization": f"Bearer {base_token}"},
            json={"store_id": str(store_a1.id.value)},
        )
        assert select_a1.status_code == 200, select_a1.text
        token_a1 = select_a1.json()["access_token"]
        assert select_a1.json()["selected_store_id"] == str(store_a1.id.value)
        assert token_a1 != base_token

        me_a1 = await client.get("/me", headers={"Authorization": f"Bearer {token_a1}"})
        assert me_a1.status_code == 200
        assert me_a1.json()["corporate_id"] == str(corporate.id.value)
        assert me_a1.json()["person_id"] == str(person.id.value)
        assert me_a1.json()["selected_store_id"] == str(store_a1.id.value)

        # TC-095 & TC-107: A1 トークンから A2 を選択して新トークンを発行しても、元の A1 トークンは A1 のまま独立維持
        select_a2 = await client.post(
            "/auth/store-context",
            headers={"Authorization": f"Bearer {token_a1}"},
            json={"store_id": str(store_a2.id.value)},
        )
        assert select_a2.status_code == 200, select_a2.text
        token_a2 = select_a2.json()["access_token"]
        assert select_a2.json()["selected_store_id"] == str(store_a2.id.value)

        me_a1_still = await client.get(
            "/me", headers={"Authorization": f"Bearer {token_a1}"}
        )
        me_a2 = await client.get("/me", headers={"Authorization": f"Bearer {token_a2}"})
        assert me_a1_still.json()["selected_store_id"] == str(store_a1.id.value)
        assert me_a2.json()["selected_store_id"] == str(store_a2.id.value)

        # TC-097: 非許可店舗・他法人店舗の選択は 404 で拒否、既存トークン内容不変
        for invalid_store_id in (
            str(store_a3_unpermitted.id.value),
            str(store_b1.id.value),
            "not-a-uuid",
        ):
            bad_resp = await client.post(
                "/auth/store-context",
                headers={"Authorization": f"Bearer {token_a1}"},
                json={"store_id": invalid_store_id},
            )
            assert bad_resp.status_code == 404, bad_resp.text

        # TC-097: 本文に余計な項目（corporate_id や role）を混ぜた改ざんは 422 で拒否
        tampered_body = await client.post(
            "/auth/store-context",
            headers={"Authorization": f"Bearer {token_a1}"},
            json={
                "store_id": str(store_a1.id.value),
                "corporate_id": str(other_corporate.id.value),
                "role": "corporate_admin",
            },
        )
        assert tampered_body.status_code == 422

        # 改ざん試行後も token_a1 は A1 のまま不変
        me_after_tamper = await client.get(
            "/me",
            headers={
                "Authorization": f"Bearer {token_a1}",
                "X-Store-Id": str(store_b1.id.value),
                "X-Corporate-Id": str(other_corporate.id.value),
                "X-Actor-Role": "vendor_system_admin",
            },
        )
        assert me_after_tamper.status_code == 200
        assert me_after_tamper.json()["corporate_id"] == str(corporate.id.value)
        assert me_after_tamper.json()["selected_store_id"] == str(store_a1.id.value)
        assert me_after_tamper.json()["roles"] == ["store_operator"]


@pytest.mark.asyncio
async def test_TC096_店舗未選択トークンで店舗業務は409拒否され法人管理者の管理操作は可能(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(_NOW)
    corporate = create_corporate(name="TC096法人")
    store_a1 = create_store(corporate_id=corporate.id, name="A1店舗", code="A01")
    patient = create_patient(corporate_id=corporate.id)

    person = _person(corporate.id, "管理者")
    subject = "local:tc096-admin"
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(subject),
    )
    staff = replace(
        create_staff(corporate_id=corporate.id, code="ST096"),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(id=staff.id, corporate_id=corporate.id, person_id=person.id)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.CORPORATE_ADMIN,
        staff_id=staff.id,
        store_ids=frozenset({store_a1.id}),
    )
    assignment = create_manager_assignment(
        corporate_id=corporate.id,
        store_id=store_a1.id,
        staff_id=staff.id,
        person_id=person.id,
    )
    record = finalize_record_with_review(
        create_record(
            corporate_id=corporate.id,
            store_id=store_a1.id,
            patient_id=patient.id,
            counselor_id=staff.id,
        ),
        finalized_by=staff.id,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store_a1)
        await repos.patient.save(patient)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.membership.save(membership)
        await repos.manager_assignment.save(assignment)
        await save_history_event(repos, record)
        await repos.medication_history.save(record)
        await work.commit()

    unselected_token = await _login_Ready(
        session_factory,
        clock,
        corporate_id=corporate.id,
        email="tc096@example.com",
        subject=subject,
    )
    app = _local_auth_app(engine, session_factory, clock)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {unselected_token}"},
    ) as client:
        # 店舗業務の一覧・詳細・更新・NSIPS はすべて 409 STORE_CONTEXT_REQUIRED
        hist_list = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient.id.value}/medication-histories"
        )
        assert hist_list.status_code == 409, hist_list.text
        assert hist_list.json()["code"] == "STORE_CONTEXT_REQUIRED"

        hist_detail = await client.get(
            f"/corporates/{corporate.id.value}/medication-histories/{record.id.value}"
        )
        assert hist_detail.status_code == 409, hist_detail.text
        assert hist_detail.json()["code"] == "STORE_CONTEXT_REQUIRED"

        event_detail = await client.get(
            f"/corporates/{corporate.id.value}/events/{record.event_id.value}"
        )
        assert event_detail.status_code == 409, event_detail.text

        create_event = await client.post(
            f"/corporates/{corporate.id.value}/events",
            json={
                "store_id": str(store_a1.id.value),
                "patient_id": str(patient.id.value),
                "event_type_id": str(EventTypeId.generate().value),
                "occurred_at": _NOW.isoformat(),
            },
        )
        assert create_event.status_code == 409, create_event.text

        nsips_resp = await client.post(
            f"/corporates/{corporate.id.value}/stores/{store_a1.id.value}/integrations/nsips",
            json={
                "reception_id": str(EventId.generate().value),
                "raw_nsips_text": "NSIPS dummy",
            },
        )
        assert nsips_resp.status_code == 409, nsips_resp.text
        assert nsips_resp.json()["code"] == "STORE_CONTEXT_REQUIRED"

        # 一方、法人管理者による法人設定・店舗・Staff管理は未選択トークンでも成功する
        corp_get = await client.get(f"/corporates/{corporate.id.value}")
        assert corp_get.status_code == 200, corp_get.text

        policy_put = await client.put(
            f"/corporates/{corporate.id.value}/policy",
            json={
                "require_prescription_audit": {
                    "value": True,
                    "overridable": True,
                },
                "prohibit_self_verification": {
                    "value": False,
                    "overridable": True,
                },
            },
        )
        assert policy_put.status_code in (200, 204), policy_put.text

        stores_list = await client.get(f"/corporates/{corporate.id.value}/stores")
        assert stores_list.status_code == 200, stores_list.text

        staff_list = await client.get(f"/corporates/{corporate.id.value}/staffs")
        assert staff_list.status_code == 200, staff_list.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "revocation_kind",
    [
        "affiliation_ended",
        "store_permission_suspended",
        "store_suspended",
        "staff_retired",
    ],
)
async def test_TC098_店舗選択トークン取得後に所属終了や権限停止や店舗停止や退職が起きると次要求で拒否される(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    revocation_kind: str,
) -> None:
    clock = FakeClock(_NOW)
    corporate = create_corporate(name=f"TC098法人_{revocation_kind}")
    store_a1 = create_store(corporate_id=corporate.id, name="A1店舗", code="A01")
    patient = create_patient(corporate_id=corporate.id)

    person = _person(corporate.id)
    subject = f"local:tc098-{revocation_kind}"
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(subject),
    )
    staff = replace(
        create_staff(corporate_id=corporate.id, code="ST098"),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(id=staff.id, corporate_id=corporate.id, person_id=person.id)
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.STORE_OPERATOR,
        staff_id=staff.id,
        store_ids=frozenset({store_a1.id}),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.store.save(store_a1)
        await repos.patient.save(patient)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff_person_link.save(link)
        await repos.membership.save(membership)
        await work.commit()

    base_token = await _login_Ready(
        session_factory,
        clock,
        corporate_id=corporate.id,
        email=f"tc098-{revocation_kind}@example.com",
        subject=subject,
    )
    app = _local_auth_app(engine, session_factory, clock)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        select_resp = await client.post(
            "/auth/store-context",
            headers={"Authorization": f"Bearer {base_token}"},
            json={"store_id": str(store_a1.id.value)},
        )
        assert select_resp.status_code == 200
        token_a1 = select_resp.json()["access_token"]

        # 失効前は業務一覧取得が 200 で通る
        ok_resp = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient.id.value}/medication-histories",
            headers={"Authorization": f"Bearer {token_a1}"},
        )
        assert ok_resp.status_code == 200

        # 状態変更を保存
        async with PostgresUnitOfWork(session_factory) as work:
            repos = PostgresRepositorySet.create(work)
            if revocation_kind == "affiliation_ended":
                loaded_staff = await repos.staff.get(
                    corporate_id=corporate.id, staff_id=staff.id
                )
                assert loaded_staff is not None
                await repos.staff.save(
                    replace(
                        loaded_staff,
                        affiliations=(
                            StoreAffiliation(
                                store_id=store_a1.id,
                                is_primary=True,
                                period=AffiliationPeriod(
                                    start_date=date(2026, 1, 1),
                                    end_date=date(2026, 10, 28),
                                ),
                            ),
                        ),
                    )
                )
            elif revocation_kind == "store_permission_suspended":
                loaded_mem = await repos.membership.get(membership.id)
                assert loaded_mem is not None
                await repos.membership.save(
                    replace(loaded_mem, suspended_store_ids=frozenset({store_a1.id}))
                )
            elif revocation_kind == "store_suspended":
                loaded_store = await repos.store.get(store_a1.id)
                assert loaded_store is not None
                await repos.store.save(
                    replace(loaded_store, status=StoreStatus.SUSPENDED)
                )
            elif revocation_kind == "staff_retired":
                loaded_staff = await repos.staff.get(
                    corporate_id=corporate.id, staff_id=staff.id
                )
                loaded_acc = await repos.user_account.get(account.id)
                loaded_mem = await repos.membership.get(membership.id)
                assert loaded_staff and loaded_acc and loaded_mem
                await repos.staff.save(
                    loaded_staff.deactivate(retired_on=date(2026, 10, 28))
                )
                await repos.user_account.save(
                    replace(loaded_acc, status=AccountStatus.SUSPENDED)
                )
                await repos.membership.save(
                    replace(loaded_mem, status=AccountStatus.SUSPENDED)
                )
            await work.commit()

        # 再ログインなしでも次の要求で即座に拒否される
        denied_resp = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient.id.value}/medication-histories",
            headers={"Authorization": f"Bearer {token_a1}"},
        )
        assert denied_resp.status_code in (401, 403), denied_resp.text


@pytest.mark.asyncio
async def test_TC099_TC100_TC101_TC102_選択1店舗によるSQL隔離と他店404隠蔽と患者資格共有(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(_NOW)
    corporate = create_corporate(name="TC099法人A")
    other_corporate = create_corporate(name="TC099法人B")
    store_a1 = create_store(corporate_id=corporate.id, name="A1選択店", code="A01")
    store_a2 = create_store(
        corporate_id=corporate.id, name="A2非選択許可店", code="A02"
    )
    store_b1 = create_store(
        corporate_id=other_corporate.id, name="B1他法人店", code="B01"
    )

    patient_a = create_patient(corporate_id=corporate.id)
    coverage_a = create_coverage(corporate_id=corporate.id, patient_id=patient_a.id)
    patient_b = create_patient(corporate_id=other_corporate.id)

    person = _person(corporate.id, "兼務薬剤師")
    subject = "local:tc099-pharmacist"
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corporate.id,
        person_id=person.id,
        external_subject=ExternalSubjectKey(subject),
    )
    staff = replace(
        create_staff(corporate_id=corporate.id, code="ST099"),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("999001"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
            StoreAffiliation(
                store_id=store_a2.id,
                is_primary=False,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    link = StaffPersonLink(id=staff.id, corporate_id=corporate.id, person_id=person.id)
    # 法人管理者かつ A1/A2 両方の店舗権限を持つ Actor でも、A1 選択中は A1 のみに隔離されることを検証
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=account.id,
        corporate_id=corporate.id,
        role=MembershipRole.CORPORATE_ADMIN,
        staff_id=staff.id,
        store_ids=frozenset({store_a1.id, store_a2.id}),
    )
    mgr_person = _person(corporate.id, "管理薬剤師")
    mgr_staff = replace(
        create_staff(corporate_id=corporate.id, code="STMGR99"),
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("999002"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store_a1.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )
    mgr_link = StaffPersonLink(
        id=mgr_staff.id, corporate_id=corporate.id, person_id=mgr_person.id
    )
    mgr_a1 = create_manager_assignment(
        corporate_id=corporate.id,
        store_id=store_a1.id,
        staff_id=mgr_staff.id,
        person_id=mgr_person.id,
    )

    # A1, A2, B1 それぞれに処方・調剤・薬歴・Event を用意
    rx_a1 = create_prescription(
        corporate_id=corporate.id,
        store_id=store_a1.id,
        patient_id=patient_a.id,
        document_number="DOC-A1-001",
    )
    disp_a1 = create_dispensing(
        corporate_id=corporate.id,
        store_id=store_a1.id,
        prescription_id=rx_a1.id,
        patient_id=patient_a.id,
        dispenser_id=staff.id,
    )
    rec_a1 = replace(
        finalize_record_with_review(
            create_record(
                corporate_id=corporate.id,
                store_id=store_a1.id,
                patient_id=patient_a.id,
                prescription_id=rx_a1.id,
                dispensing_id=disp_a1.id,
                counselor_id=staff.id,
            ),
            finalized_by=staff.id,
        ),
        external_corrections=(
            ExternalPrescriptionCorrection(
                correction_id=ExternalCorrectionId("corr-a1"),
                kind=ExternalCorrectionKind.UPDATE,
                source_document_number=CorrectionDocumentNumber("DOC-A1-001"),
                reason=ExternalCorrectionReason("A1訂正理由"),
                corrected_at=ExternalCorrectionTimestamp(_NOW),
            ),
        ),
    )

    rx_a2 = create_prescription(
        corporate_id=corporate.id,
        store_id=store_a2.id,
        patient_id=patient_a.id,
        document_number="DOC-A2-001",
    )
    disp_a2 = create_dispensing(
        corporate_id=corporate.id,
        store_id=store_a2.id,
        prescription_id=rx_a2.id,
        patient_id=patient_a.id,
        dispenser_id=staff.id,
    )
    rec_a2 = replace(
        finalize_record_with_review(
            create_record(
                corporate_id=corporate.id,
                store_id=store_a2.id,
                patient_id=patient_a.id,
                prescription_id=rx_a2.id,
                dispensing_id=disp_a2.id,
                counselor_id=staff.id,
            ),
            finalized_by=staff.id,
        ),
        external_corrections=(
            ExternalPrescriptionCorrection(
                correction_id=ExternalCorrectionId("corr-a2"),
                kind=ExternalCorrectionKind.UPDATE,
                source_document_number=CorrectionDocumentNumber("DOC-A2-001"),
                reason=ExternalCorrectionReason("A2秘匿訂正理由"),
                corrected_at=ExternalCorrectionTimestamp(_NOW),
            ),
        ),
    )

    rx_b1 = create_prescription(
        corporate_id=other_corporate.id,
        store_id=store_b1.id,
        patient_id=patient_b.id,
        document_number="DOC-B1-001",
    )
    disp_b1 = create_dispensing(
        corporate_id=other_corporate.id,
        store_id=store_b1.id,
        prescription_id=rx_b1.id,
        patient_id=patient_b.id,
    )
    rec_b1 = finalize_record_with_review(
        create_record(
            corporate_id=other_corporate.id,
            store_id=store_b1.id,
            patient_id=patient_b.id,
            prescription_id=rx_b1.id,
            dispensing_id=disp_b1.id,
        )
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corporate)
        await repos.corporate.save(other_corporate)
        for st in (store_a1, store_a2, store_b1):
            await repos.store.save(st)
        await repos.patient.save(patient_a)
        await repos.patient_coverage.save(coverage_a)
        await repos.patient.save(patient_b)
        await repos.account_person.save(person)
        await repos.account_person.save(mgr_person)
        await repos.user_account.save(account)
        await repos.staff.save(staff)
        await repos.staff.save(mgr_staff)
        await repos.staff_person_link.save(link)
        await repos.staff_person_link.save(mgr_link)
        await repos.membership.save(membership)
        await repos.manager_assignment.save(mgr_a1)

        await repos.prescription.save(rx_a1)
        await repos.dispensing.save(disp_a1)
        await save_history_event(repos, rec_a1)
        await repos.medication_history.save(rec_a1)

        await repos.prescription.save(rx_a2)
        await repos.dispensing.save(disp_a2)
        await save_history_event(repos, rec_a2)
        await repos.medication_history.save(rec_a2)

        await repos.prescription.save(rx_b1)
        await repos.dispensing.save(disp_b1)
        await save_history_event(repos, rec_b1)
        await repos.medication_history.save(rec_b1)

        definitions = await repos.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        follow_up_def = next(
            item
            for item in definitions
            if item.corporate_id is None
            and item.standard_code is not None
            and item.standard_code.value == "medication_period_follow_up"
        )
        linked_a1_event = Event(
            id=EventId.generate(),
            event_type_id=follow_up_def.id,
            event_type_standard_code=follow_up_def.standard_code,
            event_type_name=follow_up_def.name,
            corporate_id=corporate.id,
            store_id=store_a1.id,
            patient_id=patient_a.id,
            occurred_at=EventOccurredTimestamp(_NOW),
            created_at=EventCreatedTimestamp(_NOW),
            related_event_id=rec_a2.event_id,
        )
        await repos.event.save(linked_a1_event)
        await work.commit()

    base_token = await _login_Ready(
        session_factory,
        clock,
        corporate_id=corporate.id,
        email="tc099@example.com",
        subject=subject,
    )
    app = _local_auth_app(engine, session_factory, clock)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        select_a1 = await client.post(
            "/auth/store-context",
            headers={"Authorization": f"Bearer {base_token}"},
            json={"store_id": str(store_a1.id.value)},
        )
        assert select_a1.status_code == 200
        token_a1 = select_a1.json()["access_token"]
        headers_a1 = {"Authorization": f"Bearer {token_a1}"}

        # TC-099: 患者の薬歴一覧は A1 のみ返り、A2/B1 は含まれない
        histories = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient_a.id.value}/medication-histories",
            headers=headers_a1,
        )
        assert histories.status_code == 200, histories.text
        assert [item["id"] for item in histories.json()] == [str(rec_a1.id.value)]

        # TC-099: 外部訂正一覧も A1 のみ返り、カーソルや件数に A2 が混ざらない
        corrections = await client.get(
            f"/corporates/{corporate.id.value}/medication-history-external-corrections",
            headers=headers_a1,
        )
        assert corrections.status_code == 200, corrections.text
        assert [item["record_id"] for item in corrections.json()["items"]] == [
            str(rec_a1.id.value)
        ]
        assert corrections.json()["next_cursor"] is None
        assert "A2秘匿訂正理由" not in corrections.text

        # TC-099: 関連 Event 候補一覧も A1 のみ返り、A2 Event は含まれない
        candidates = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient_a.id.value}/events/related-candidates",
            params={"store_id": str(store_a1.id.value)},
            headers=headers_a1,
        )
        assert candidates.status_code == 200, candidates.text
        assert {item["event_id"] for item in candidates.json()} == {
            str(rec_a1.event_id.value),
            str(linked_a1_event.id.value),
        }

        # A2 の store_id を指定して候補を要求すると 404
        candidates_a2 = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient_a.id.value}/events/related-candidates",
            params={"store_id": str(store_a2.id.value)},
            headers=headers_a1,
        )
        assert candidates_a2.status_code == 404

        # TC-100: A1 Event 内に他店 related_event_id があってもレスポンスに漏らさない
        linked_event_resp = await client.get(
            f"/corporates/{corporate.id.value}/events/{linked_a1_event.id.value}",
            headers=headers_a1,
        )
        assert linked_event_resp.status_code == 200
        assert linked_event_resp.json()["related_event_id"] is None

        # TC-100: A2 / B1 の Event・処方・調剤・薬歴・フォローアップ元を直指定するとすべて 404
        for path in (
            f"/corporates/{corporate.id.value}/events/{rec_a2.event_id.value}",
            f"/corporates/{corporate.id.value}/prescriptions/{rx_a2.id.value}",
            f"/corporates/{corporate.id.value}/dispensings/{disp_a2.id.value}",
            f"/corporates/{corporate.id.value}/medication-histories/{rec_a2.id.value}",
            f"/corporates/{corporate.id.value}/medication-histories/{rec_a2.id.value}/view",
            f"/corporates/{other_corporate.id.value}/prescriptions/{rx_b1.id.value}",
            f"/corporates/{other_corporate.id.value}/medication-histories/{rec_b1.id.value}",
        ):
            r = await client.get(path, headers=headers_a1)
            assert r.status_code == 404, f"{path} returned {r.status_code}: {r.text}"

        # TC-101: 患者基本台帳・保険資格は法人共有として取得可、他店舗業務記録は同梱しない。他法人は 404
        pat_resp = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient_a.id.value}",
            headers=headers_a1,
        )
        assert pat_resp.status_code == 200, pat_resp.text
        assert pat_resp.json()["id"] == str(patient_a.id.value)

        cov_resp = await client.get(
            f"/corporates/{corporate.id.value}/patients/{patient_a.id.value}/coverages",
            headers=headers_a1,
        )
        assert cov_resp.status_code == 200, cov_resp.text
        assert len(cov_resp.json()) == 1

        other_pat_resp = await client.get(
            f"/corporates/{other_corporate.id.value}/patients/{patient_b.id.value}",
            headers=headers_a1,
        )
        assert other_pat_resp.status_code == 404

        # TC-102: A1 トークンで A2 の処方・調剤・薬歴を更新、または store_id 偽装しても 404 で A1/A2 双方不変
        rx_a2_ver = await _row_version(engine, "prescriptions", rx_a2.id.value)
        disp_a2_ver = await _row_version(
            engine, "dispensing_processes", disp_a2.id.value
        )
        rec_a2_ver = await _row_version(
            engine, "medication_history_records", rec_a2.id.value
        )

        cancel_rx_a2 = await client.post(
            f"/corporates/{corporate.id.value}/prescriptions/{rx_a2.id.value}/cancellation",
            headers=headers_a1,
            json={"reason": "A1からA2処方を取消試行"},
        )
        assert cancel_rx_a2.status_code == 404

        verify_disp_a2 = await client.post(
            f"/corporates/{corporate.id.value}/dispensings/{disp_a2.id.value}/verification",
            headers=headers_a1,
            json={"result": "passed"},
        )
        assert verify_disp_a2.status_code == 404

        amend_rec_a2 = await client.post(
            f"/corporates/{corporate.id.value}/medication-histories/{rec_a2.id.value}/amendments",
            headers=headers_a1,
            json={
                "reason": "A1からA2薬歴を訂正試行",
                "amended_soap": {
                    "subjective": [{"text": "改ざん"}],
                    "objective": [],
                    "assessment": [],
                    "plan": [],
                },
            },
        )
        assert amend_rec_a2.status_code == 404

        # フォローアップで A2 の薬歴 ID を指定しつつ body.store_id だけ A1 に偽装しても 404
        forged_follow_up = await client.post(
            f"/corporates/{corporate.id.value}/medication-histories/{rec_a2.id.value}/follow-ups",
            headers=headers_a1,
            json={
                "store_id": str(store_a1.id.value),
                "patient_id": str(patient_a.id.value),
                "followed_up_at": _NOW.isoformat(),
                "method": "in_person",
                "soap": {
                    "subjective": [{"text": "偽装フォローアップ"}],
                    "objective": [],
                    "assessment": [],
                    "plan": [],
                },
            },
        )
        assert forged_follow_up.status_code == 404

        assert await _row_version(engine, "prescriptions", rx_a2.id.value) == rx_a2_ver
        assert (
            await _row_version(engine, "dispensing_processes", disp_a2.id.value)
            == disp_a2_ver
        )
        assert (
            await _row_version(engine, "medication_history_records", rec_a2.id.value)
            == rec_a2_ver
        )


async def _row_version(engine: AsyncEngine, table: str, row_id: UUID) -> int:
    async with engine.connect() as conn:
        val = await conn.scalar(
            text(f"SELECT version FROM {table} WHERE id = :id"),
            {"id": row_id},
        )
        assert isinstance(val, int)
        return val
