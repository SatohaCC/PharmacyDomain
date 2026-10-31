"""法人・店舗ポリシーのトランザクション・永続化・並行競合の実DBテスト（TC-070, TC-080）。"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.boundary_models import (
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingCommand,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.value_objects import CorporatePolicy, PolicySetting
from app.domain.dispensing.exceptions import SelfVerificationProhibitedConflictError
from app.domain.dispensing.primitives import (
    DispensingCompletionType,
    DispensingProcessStatus,
)
from app.domain.identity.entities import StaffPersonLink, UserAccount
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.identifiers import StoreId
from app.domain.store.value_objects import StorePolicy
from app.infrastructure.corporate.postgres.corporate import PostgresCorporateRepository
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.dispensing.postgres.dispensing_process import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.postgres.connection import PostgresSettings, PostgresUnitOfWork
from app.infrastructure.prescription.postgres.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.store.postgres.store import PostgresStoreRepository
from tests.factories.dispensing_factory import create_dispensing, verify_passed
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate
from tests.integration.test_identity_persistence import _person


@pytest.mark.integration
async def test_TC070_CorporateおよびStoreポリシーが同一集約JSONBに永続化され別UoWで復元される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """TC-070: Corporate/Store集約内のJSONB payloadへの保存と復元（専用表不要）。"""
    corporate = create_corporate("ポリシー永続化テスト薬局")
    corporate_policy = CorporatePolicy(
        require_prescription_audit=PolicySetting(value=True, overridable=False),
        prohibit_self_verification=PolicySetting(value=False, overridable=True),
    )
    corporate = corporate.change_policy(corporate_policy)

    store = create_store(corporate_id=corporate.id)
    store_policy = StorePolicy(
        require_prescription_audit=None,
        prohibit_self_verification=True,
    )
    store = store.change_policy(store_policy)

    # 1. 保存
    uow_write = PostgresUnitOfWork(session_factory)
    async with uow_write:
        corp_repo = PostgresCorporateRepository(uow_write)
        store_repo = PostgresStoreRepository(uow_write)
        await corp_repo.save(corporate)
        await store_repo.save(store)
        await uow_write.commit()

    # 2. 別UoWで再取得して集約モデルの復元を検証
    uow_read = PostgresUnitOfWork(session_factory)
    async with uow_read:
        corp_repo = PostgresCorporateRepository(uow_read)
        store_repo = PostgresStoreRepository(uow_read)
        loaded_corp = await corp_repo.get(corporate.id)
        loaded_store = await store_repo.get(store.id)

    assert loaded_corp is not None
    assert loaded_corp.policy == corporate_policy
    assert loaded_corp.policy.require_prescription_audit.value is True
    assert loaded_corp.policy.require_prescription_audit.overridable is False
    assert loaded_corp.policy.prohibit_self_verification.value is False
    assert loaded_corp.policy.prohibit_self_verification.overridable is True

    assert loaded_store is not None
    assert loaded_store.policy == store_policy
    assert loaded_store.policy.require_prescription_audit is None
    assert loaded_store.policy.prohibit_self_verification is True

    # 3. 専用表が存在せず、JSONB payloadに格納されていることを生SQLで検証
    async with session_factory() as session:
        corp_row = await session.execute(
            text("SELECT payload FROM corporates WHERE id = :id"),
            {"id": corporate.id.value},
        )
        corp_payload = corp_row.scalar_one()
        assert "policy" in corp_payload
        assert corp_payload["policy"]["require_prescription_audit"]["value"] is True
        assert (
            corp_payload["policy"]["require_prescription_audit"]["overridable"] is False
        )

        store_row = await session.execute(
            text("SELECT payload FROM stores WHERE id = :id"),
            {"id": store.id.value},
        )
        store_payload = store_row.scalar_one()
        assert "policy" in store_payload
        assert store_payload["policy"]["require_prescription_audit"] is None
        assert store_payload["policy"]["prohibit_self_verification"] is True


def _vendor_admin_auth(
    person_id: AccountPersonId,
    account_id: UserAccountId,
    *,
    corporate_id: CorporateId | None = None,
    staff_id: StaffId | None = None,
    store_id: StoreId | None = None,
) -> AuthorizationService:
    return AuthorizationService(
        ResolvedActorContext(
            principal_id="integration-vendor-admin",
            roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
            person_id=person_id,
            account_id=account_id,
            corporate_id=corporate_id,
            staff_id=staff_id,
            store_ids=frozenset({store_id}) if store_id else frozenset(),
            selected_store_id=store_id,
        )
    )


@pytest.mark.integration
async def test_TC080_自己鑑査禁止ポリシー強化と交付完了の並行競合(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> None:
    """TC-080: 交付先行なら完了、強化先行なら409、完了済み履歴は後から取り消さない。"""
    corp_id = CorporateId.generate()
    corporate = create_corporate("競合テスト薬局")
    corporate = replace(corporate, id=corp_id)

    person = _person(corporate_id=corp_id)
    account = UserAccount(
        id=UserAccountId.generate(),
        corporate_id=corp_id,
        person_id=person.id,
        is_vendor_admin=True,
    )
    store = create_store(corporate_id=corp_id)

    # 同一自然人（person.id）を調剤者と鑑査者に割り当てる
    dispenser_id = StaffId.generate()
    verifier_id = StaffId.generate()

    auth = _vendor_admin_auth(
        person.id,
        account.id,
        corporate_id=corp_id,
        staff_id=dispenser_id,
        store_id=store.id,
    )

    link_dispenser = StaffPersonLink(
        id=dispenser_id, corporate_id=corp_id, person_id=person.id
    )
    link_verifier = StaffPersonLink(
        id=verifier_id, corporate_id=corp_id, person_id=person.id
    )

    # 処方箋と調剤プロセス（自己鑑査合格済み）
    prescription_1 = create_prescription(corporate_id=corp_id).ready_for_dispensing()
    prescription_1 = replace(prescription_1, store_id=store.id)

    process_1 = create_dispensing(
        corporate_id=corp_id,
        prescription_id=prescription_1.id,
        dispenser_id=dispenser_id,
    )
    process_1 = replace(process_1, store_id=store.id)
    process_1 = verify_passed(process_1, verifier_id=verifier_id)

    # 処方箋2と調剤プロセス2（強化先行テスト用）
    prescription_2 = create_prescription(corporate_id=corp_id).ready_for_dispensing()
    prescription_2 = replace(prescription_2, store_id=store.id)

    process_2 = create_dispensing(
        corporate_id=corp_id,
        prescription_id=prescription_2.id,
        dispenser_id=dispenser_id,
    )
    process_2 = replace(process_2, store_id=store.id)
    process_2 = verify_passed(process_2, verifier_id=verifier_id)

    # スタッフ集約（FK整合性のため先に保存）
    staff_dispenser = replace(
        create_staff(corporate_id=corp_id),
        id=dispenser_id,
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
    staff_verifier = replace(
        create_staff(corporate_id=corp_id),
        id=verifier_id,
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123457"))
        ),
        affiliations=(
            StoreAffiliation(
                store_id=store.id,
                is_primary=True,
                period=AffiliationPeriod(start_date=date(2026, 1, 1)),
            ),
        ),
    )

    # 初期データを保存（法人は自己鑑査許容: prohibit_self_verification=False）
    corporate = corporate.change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=False),
            prohibit_self_verification=PolicySetting(value=False, overridable=False),
        )
    )

    uow_init = PostgresUnitOfWork(session_factory)
    async with uow_init:
        await PostgresCorporateRepository(uow_init).save(corporate)
        repos = PostgresRepositorySet.create(uow_init)
        await repos.store.save(store)
        await repos.account_person.save(person)
        await repos.user_account.save(account)
        await repos.staff.save(staff_dispenser)
        await repos.staff.save(staff_verifier)
        await repos.staff_person_link.save(link_dispenser)
        await repos.staff_person_link.save(link_verifier)
        await PostgresPrescriptionRepository(uow_init).save(prescription_1)
        await PostgresDispensingProcessRepository(uow_init).save(process_1)
        await PostgresPrescriptionRepository(uow_init).save(prescription_2)
        await PostgresDispensingProcessRepository(uow_init).save(process_2)
        await uow_init.commit()

    root = PostgresCompositionRoot.from_settings(postgres_settings)
    try:
        # パターン1: 交付先行 (Delivery first)
        # 1. 交付完了を実行 -> 成功して completed に遷移
        async with root.request_scope(authorization=auth) as scope:
            await scope.use_cases.dispensing.complete.execute(
                CompleteDispensingCommand(
                    corporate_id=str(corp_id.value),
                    dispensing_id=str(process_1.id.value),
                    completion_type=DispensingCompletionType.COMPLETED.value,
                )
            )

        # 2. その後、法人が自己鑑査禁止を強化（prohibit_self_verification=True）
        strengthened_policy = CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=False),
            prohibit_self_verification=PolicySetting(value=True, overridable=False),
        )
        uow_policy = PostgresUnitOfWork(session_factory)
        async with uow_policy:
            corp_repo = PostgresCorporateRepository(uow_policy)
            loaded_corp = await corp_repo.get(corporate_id=corp_id)
            assert loaded_corp is not None
            corporate_strengthened = loaded_corp.change_policy(strengthened_policy)
            await corp_repo.save(corporate_strengthened)
            await uow_policy.commit()

        # 3. 先行して完了済みの process_1 は COMPLETED のまま不変（取り消されない）
        uow_check_1 = PostgresUnitOfWork(session_factory)
        async with uow_check_1:
            stored_1 = await PostgresDispensingProcessRepository(uow_check_1).get(
                corporate_id=corp_id, dispensing_id=process_1.id
            )
            assert stored_1 is not None
            assert stored_1.status is DispensingProcessStatus.COMPLETED

        # パターン2: 強化先行 (Policy strengthening first)
        # すでに prohibit_self_verification=True に強化されている状態で、自己鑑査合格の process_2 を交付完了しようとする
        with pytest.raises(SelfVerificationProhibitedConflictError):
            async with root.request_scope(authorization=auth) as scope:
                await scope.use_cases.dispensing.complete.execute(
                    CompleteDispensingCommand(
                        corporate_id=str(corp_id.value),
                        dispensing_id=str(process_2.id.value),
                        completion_type=DispensingCompletionType.COMPLETED.value,
                    )
                )

        # process_2 は完了せず VERIFIED のまま不変
        uow_check_2 = PostgresUnitOfWork(session_factory)
        async with uow_check_2:
            stored_2 = await PostgresDispensingProcessRepository(uow_check_2).get(
                corporate_id=corp_id, dispensing_id=process_2.id
            )
            assert stored_2 is not None
            assert stored_2.status is DispensingProcessStatus.VERIFIED

    finally:
        await root.dispose()
