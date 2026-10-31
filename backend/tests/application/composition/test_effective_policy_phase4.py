"""Phase 4: 法人・店舗ポリシーのユニットテスト（TC-069, TC-071, TC-072, TC-073, TC-076, TC-077, TC-078, TC-079, TC-081）。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.composition.adapters.effective_policy_resolver import (
    EffectivePolicyResolver,
)
from app.application.composition.adapters.staff_person_adapter import (
    StaffPersonAdapter,
)
from app.application.corporate.commands.update_corporate_policy import (
    PolicySettingInput,
    UpdateCorporatePolicyCommand,
    UpdateCorporatePolicyUseCase,
)
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingCommand,
)
from app.application.dispensing.commands.record_audit import RecordAuditCommand
from app.application.dispensing.commands.verify_dispensing import (
    VerifyDispensingCommand,
)
from app.application.dispensing.interfaces.references import (
    DispensingPolicySnapshot,
)
from app.application.store.commands.update_store_policy import (
    UpdateStorePolicyCommand,
    UpdateStorePolicyUseCase,
)
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateName
from app.domain.corporate.value_objects import (
    CorporatePolicy,
    CorporateRepresentativeName,
    PolicySetting,
)
from app.domain.dispensing.exceptions import (
    DispensingPharmacistQualificationError,
    PrescriptionAuditRequiredConflictError,
    SelfVerificationProhibitedConflictError,
    VerificationNotPassedError,
)
from app.domain.identity.entities import StaffPersonLink
from app.domain.shared.actor import AccountPersonId
from app.domain.shared.person_name import PersonNamePart
from app.domain.staff.identifiers import StaffId
from app.domain.staff.value_objects import StaffQualifications
from app.domain.store.entities import Store
from app.domain.store.exceptions import StorePolicyOverrideConflictError
from app.domain.store.identifiers import StoreId
from app.domain.store.value_objects import (
    StorePolicy,
)
from tests.application.access_helpers import (
    create_corporate_admin_access_for,
)
from tests.application.dispensing.helpers import (
    create_fixture,
    create_pharmacist_qualifications,
    create_resolved_actor,
    create_start_command,
)
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.fakes.in_memory_identity_repositories import (
    InMemoryStaffPersonLinkRepository,
)
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


def _make_store(corporate_id: CorporateId, store_id: StoreId | None = None) -> Store:
    sid = store_id or StoreId.generate()
    store = create_store(
        corporate_id=corporate_id,
        name=f"店舗-{str(sid.value)}",
    )
    if store_id is not None:
        return replace(store, id=store_id)
    return store


def _make_corporate(corporate_id: CorporateId | None = None) -> Corporate:
    cid = corporate_id or CorporateId.generate()
    return Corporate(
        id=cid,
        name=CorporateName(f"テスト法人-{str(cid.value)}"),
        representative_name=CorporateRepresentativeName(
            last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
        ),
    )


class _StaticPolicyBoundary:
    def __init__(self, snapshot: DispensingPolicySnapshot) -> None:
        self.snapshot = snapshot

    async def get_effective_policy(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> DispensingPolicySnapshot:
        return self.snapshot


@pytest.mark.asyncio
async def test_TC069_既定ポリシー_新法人新店舗で両項目falseかつoverridable_falseかつ店舗null() -> (
    None
):
    corp = _make_corporate()
    store = _make_store(corp.id)

    # 1. Corporate集約の既定値
    assert corp.policy.require_prescription_audit.value is False
    assert corp.policy.require_prescription_audit.overridable is False
    assert corp.policy.prohibit_self_verification.value is False
    assert corp.policy.prohibit_self_verification.overridable is False

    # 2. Store集約の既定値
    assert store.policy.require_prescription_audit is None
    assert store.policy.prohibit_self_verification is None

    # 3. 実効値の解決
    corp_repo = InMemoryCorporateRepository()
    await corp_repo.save(corp)
    store_repo = InMemoryStoreRepository()
    await store_repo.save(store)
    resolver = EffectivePolicyResolver(corp_repo, store_repo)

    effective = await resolver.get_effective_policy(
        corporate_id=corp.id, store_id=store.id
    )
    assert effective.require_prescription_audit is False
    assert effective.prohibit_self_verification is False


@pytest.mark.asyncio
async def test_TC071_実効値解決_法人値と店舗上書きとoverridableの全組み合わせ() -> None:
    corp_repo = InMemoryCorporateRepository()
    store_repo = InMemoryStoreRepository()
    resolver = EffectivePolicyResolver(corp_repo, store_repo)

    # パターン1: 法人false, 店舗true, overridable=False -> false
    corp1 = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=False),
            prohibit_self_verification=PolicySetting(value=False, overridable=False),
        )
    )
    store1 = _make_store(corp1.id).change_policy(
        StorePolicy(
            require_prescription_audit=True,
            prohibit_self_verification=True,
        )
    )
    await corp_repo.save(corp1)
    await store_repo.save(store1)

    eff1 = await resolver.get_effective_policy(
        corporate_id=corp1.id, store_id=store1.id
    )
    assert eff1.require_prescription_audit is False
    assert eff1.prohibit_self_verification is False

    # パターン2: 法人false, 店舗true, overridable=True -> true
    corp2 = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=True),
            prohibit_self_verification=PolicySetting(value=False, overridable=True),
        )
    )
    store2 = _make_store(corp2.id).change_policy(
        StorePolicy(
            require_prescription_audit=True,
            prohibit_self_verification=True,
        )
    )
    await corp_repo.save(corp2)
    await store_repo.save(store2)

    eff2 = await resolver.get_effective_policy(
        corporate_id=corp2.id, store_id=store2.id
    )
    assert eff2.require_prescription_audit is True
    assert eff2.prohibit_self_verification is True

    # パターン3: 法人true, 店舗false, overridable=False -> true
    corp3 = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=True, overridable=False),
            prohibit_self_verification=PolicySetting(value=True, overridable=False),
        )
    )
    store3 = _make_store(corp3.id).change_policy(
        StorePolicy(
            require_prescription_audit=False,
            prohibit_self_verification=False,
        )
    )
    await corp_repo.save(corp3)
    await store_repo.save(store3)

    eff3 = await resolver.get_effective_policy(
        corporate_id=corp3.id, store_id=store3.id
    )
    assert eff3.require_prescription_audit is True
    assert eff3.prohibit_self_verification is True

    # パターン4: 法人true, 店舗false, overridable=True -> false
    corp4 = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=True, overridable=True),
            prohibit_self_verification=PolicySetting(value=True, overridable=True),
        )
    )
    store4 = _make_store(corp4.id).change_policy(
        StorePolicy(
            require_prescription_audit=False,
            prohibit_self_verification=False,
        )
    )
    await corp_repo.save(corp4)
    await store_repo.save(store4)

    eff4 = await resolver.get_effective_policy(
        corporate_id=corp4.id, store_id=store4.id
    )
    assert eff4.require_prescription_audit is False
    assert eff4.prohibit_self_verification is False

    # パターン5: 店舗None -> 常に法人値
    store5 = _make_store(corp4.id).change_policy(
        StorePolicy(
            require_prescription_audit=None,
            prohibit_self_verification=None,
        )
    )
    await store_repo.save(store5)
    eff5 = await resolver.get_effective_policy(
        corporate_id=corp4.id, store_id=store5.id
    )
    assert eff5.require_prescription_audit is True
    assert eff5.prohibit_self_verification is True


@pytest.mark.asyncio
async def test_TC072_店舗ポリシー上書き_禁止中の非null設定は409でnull解除は成功_既存店舗値での法人禁止更新は成功() -> (
    None
):
    corp = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=False),
            prohibit_self_verification=PolicySetting(value=False, overridable=True),
        )
    )
    store = _make_store(corp.id)
    corp_repo = InMemoryCorporateRepository()
    await corp_repo.save(corp)
    store_repo = InMemoryStoreRepository()
    await store_repo.save(store)

    admin_access = create_corporate_admin_access_for(corp.id, corp_repo)
    resolver = EffectivePolicyResolver(corp_repo, store_repo)
    use_case = UpdateStorePolicyUseCase(store_repo, admin_access, resolver)

    # 1. require_prescription_audit は overridable=False なので非null値PUTは409
    with pytest.raises(StorePolicyOverrideConflictError):
        await use_case.execute(
            UpdateStorePolicyCommand(
                corporate_id=str(corp.id.value),
                store_id=str(store.id.value),
                require_prescription_audit=True,
            )
        )

    # 2. 禁止中項目でも None（解除）の指定なら成功
    await use_case.execute(
        UpdateStorePolicyCommand(
            corporate_id=str(corp.id.value),
            store_id=str(store.id.value),
            require_prescription_audit=None,
            prohibit_self_verification=True,  # これはoverridable=Trueなので成功
        )
    )
    saved_store = await store_repo.get(store.id)
    assert saved_store is not None
    assert saved_store.policy.require_prescription_audit is None
    assert saved_store.policy.prohibit_self_verification is True

    # 3. 店舗に非null値が保存されている状態で、法人がoverridable=Falseへ更新 -> 拒否されず成功する
    corp_use_case = UpdateCorporatePolicyUseCase(corp_repo, admin_access)
    await corp_use_case.execute(
        UpdateCorporatePolicyCommand(
            corporate_id=str(corp.id.value),
            require_prescription_audit=PolicySettingInput(
                value=False, overridable=False
            ),
            prohibit_self_verification=PolicySettingInput(
                value=False, overridable=False
            ),
        )
    )
    saved_corp = await corp_repo.get(corp.id)
    assert saved_corp is not None
    assert saved_corp.policy.prohibit_self_verification.overridable is False


@pytest.mark.asyncio
async def test_TC073_既存上書きの保持と復活_禁止中は法人値で再許可時に保存済み店舗値が再有効化() -> (
    None
):
    # 1. 法人がoverridable=Trueで店舗がtrueを保存
    corp = _make_corporate().change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=True),
            prohibit_self_verification=PolicySetting(value=False, overridable=True),
        )
    )
    store = _make_store(corp.id).change_policy(
        StorePolicy(
            require_prescription_audit=True,
            prohibit_self_verification=True,
        )
    )
    corp_repo = InMemoryCorporateRepository()
    await corp_repo.save(corp)
    store_repo = InMemoryStoreRepository()
    await store_repo.save(store)
    resolver = EffectivePolicyResolver(corp_repo, store_repo)

    eff = await resolver.get_effective_policy(corporate_id=corp.id, store_id=store.id)
    assert eff.require_prescription_audit is True

    # 2. 法人がoverridable=Falseに変更
    corp = corp.change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=False),
            prohibit_self_verification=PolicySetting(value=False, overridable=False),
        )
    )
    await corp_repo.save(corp)

    # 禁止中は法人値（False）が実効値になるが、店舗値は勝手に消されない
    eff_forbidden = await resolver.get_effective_policy(
        corporate_id=corp.id, store_id=store.id
    )
    assert eff_forbidden.require_prescription_audit is False

    saved_store = await store_repo.get(store.id)
    assert saved_store is not None
    assert saved_store.policy.require_prescription_audit is True

    # 3. 法人が再許可（overridable=True）
    corp = corp.change_policy(
        CorporatePolicy(
            require_prescription_audit=PolicySetting(value=False, overridable=True),
            prohibit_self_verification=PolicySetting(value=False, overridable=True),
        )
    )
    await corp_repo.save(corp)

    # 再許可で保存済み店舗値（True）が復活
    eff_restored = await resolver.get_effective_policy(
        corporate_id=corp.id, store_id=store.id
    )
    assert eff_restored.require_prescription_audit is True


@pytest.mark.asyncio
async def test_TC076_処方鑑査必須ポリシー_有効時は問題なし処方鑑査がなければ最終合格不可() -> (
    None
):
    # require_prescription_audit = True のポリシーを注入
    policy = DispensingPolicySnapshot(
        require_prescription_audit=True,
        prohibit_self_verification=False,
    )
    fixture = create_fixture(
        policy_boundary=_StaticPolicyBoundary(policy),
    )
    dispenser_id = fixture.dispenser_id
    verifier_id = fixture.verifier_id

    # 調剤開始
    start_dto = await fixture.start.execute(
        create_start_command(fixture, dispenser_id=dispenser_id)
    )

    # 1. 処方鑑査未記録で最終鑑査（合格）を要求 -> 409
    with pytest.raises(PrescriptionAuditRequiredConflictError):
        await fixture.verify.execute(
            VerifyDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=start_dto.id,
                verifier_id=str(verifier_id.value),
                result="passed",
            )
        )

    # 2. 問題あり（has_issues=True）で処方鑑査を記録 -> 依然として409
    await fixture.record_audit.execute(
        RecordAuditCommand(
            corporate_id=str(fixture.corporate_id.value),
            dispensing_id=start_dto.id,
            auditor_id=str(verifier_id.value),
            has_issues=True,
            notes="疑義あり",
        )
    )
    with pytest.raises(PrescriptionAuditRequiredConflictError):
        await fixture.verify.execute(
            VerifyDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=start_dto.id,
                verifier_id=str(verifier_id.value),
                result="passed",
            )
        )

    # 3. 問題なし（has_issues=False）で処方鑑査を記録 -> 合格成功
    await fixture.record_audit.execute(
        RecordAuditCommand(
            corporate_id=str(fixture.corporate_id.value),
            dispensing_id=start_dto.id,
            auditor_id=str(verifier_id.value),
            has_issues=False,
        )
    )
    verify_dto = await fixture.verify.execute(
        VerifyDispensingCommand(
            corporate_id=str(fixture.corporate_id.value),
            dispensing_id=start_dto.id,
            verifier_id=str(verifier_id.value),
            result="passed",
        )
    )
    assert verify_dto.status == "verified"


@pytest.mark.asyncio
async def test_TC077_自己鑑査禁止ポリシー_有効時は同一自然人による最終鑑査を409拒否() -> (
    None
):
    # StaffPersonLink のセットアップ
    person_1 = AccountPersonId.generate()
    person_2 = AccountPersonId.generate()
    link_repo = InMemoryStaffPersonLinkRepository()

    # 別スタッフ staff_other は別人物 person_2
    staff_other = StaffId.generate()

    staff_person = StaffPersonAdapter(link_repo)
    policy = DispensingPolicySnapshot(
        require_prescription_audit=False,
        prohibit_self_verification=True,
    )
    fixture = create_fixture(
        policy_boundary=_StaticPolicyBoundary(policy),
        staff_person=staff_person,
    )
    corporate_id = fixture.corporate_id
    dispenser_id = fixture.dispenser_id
    verifier_id = fixture.verifier_id

    # dispenser_id と verifier_id は同じ person_1 を参照
    await link_repo.save(
        StaffPersonLink(id=dispenser_id, corporate_id=corporate_id, person_id=person_1)
    )
    await link_repo.save(
        StaffPersonLink(id=verifier_id, corporate_id=corporate_id, person_id=person_1)
    )
    await link_repo.save(
        StaffPersonLink(id=staff_other, corporate_id=corporate_id, person_id=person_2)
    )
    fixture.staff_qualification.register(
        corporate_id=corporate_id,
        staff_id=staff_other,
        qualifications=create_pharmacist_qualifications(),
    )

    start_dto = await fixture.start.execute(
        create_start_command(fixture, dispenser_id=dispenser_id)
    )

    # 1. 調剤者と同一自然人の verifier_id で最終鑑査 -> 409
    with pytest.raises(SelfVerificationProhibitedConflictError):
        await fixture.verify.execute(
            VerifyDispensingCommand(
                corporate_id=str(corporate_id.value),
                dispensing_id=start_dto.id,
                result="passed",
            )
        )

    # 2. 異なる自然人 staff_other で最終鑑査 -> 成功
    other_fixture = create_fixture(
        prescription=fixture.prescription,
        policy_boundary=_StaticPolicyBoundary(policy),
        staff_person=staff_person,
        verifier_actor=create_resolved_actor(staff_id=staff_other),
    )
    other_fixture.repository.items.update(fixture.repository.items)
    verify_dto = await other_fixture.verify.execute(
        VerifyDispensingCommand(
            corporate_id=str(corporate_id.value),
            dispensing_id=start_dto.id,
            result="passed",
        )
    )
    assert verify_dto.status == "verified"


@pytest.mark.asyncio
async def test_TC078_ポリシーfalse回帰_無資格鑑査や未合格完了は依然として拒否される() -> (
    None
):
    policy = DispensingPolicySnapshot(
        require_prescription_audit=False,
        prohibit_self_verification=False,
    )
    unqualified_staff = StaffId.generate()
    fixture = create_fixture(
        policy_boundary=_StaticPolicyBoundary(policy),
        verifier_actor=create_resolved_actor(staff_id=unqualified_staff),
    )

    start_dto = await fixture.start.execute(create_start_command(fixture))

    # 1. 無資格スタッフはポリシーfalseでも最終鑑査不可
    fixture.staff_qualification.register(
        corporate_id=fixture.corporate_id,
        staff_id=unqualified_staff,
        qualifications=StaffQualifications.from_profiles(),
    )
    with pytest.raises(DispensingPharmacistQualificationError):
        await fixture.verify.execute(
            VerifyDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=start_dto.id,
                result="passed",
            )
        )

    # 2. 最終鑑査未合格のまま完了はポリシーfalseでも不可
    with pytest.raises(VerificationNotPassedError):
        await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=start_dto.id,
                completion_type="completed",
            )
        )


@pytest.mark.asyncio
async def test_TC079_完了前ポリシー再判定_鑑査合格後にポリシーが強化された場合は完了を拒否() -> (
    None
):
    # 初めは prohibit_self_verification=False
    dynamic_policy = DispensingPolicySnapshot(
        require_prescription_audit=False,
        prohibit_self_verification=False,
    )
    boundary = _StaticPolicyBoundary(dynamic_policy)

    person_1 = AccountPersonId.generate()
    link_repo = InMemoryStaffPersonLinkRepository()
    staff_person = StaffPersonAdapter(link_repo)

    fixture = create_fixture(
        policy_boundary=boundary,
        staff_person=staff_person,
    )
    corporate_id = fixture.corporate_id
    dispenser_id = fixture.dispenser_id
    verifier_id = fixture.verifier_id

    await link_repo.save(
        StaffPersonLink(id=dispenser_id, corporate_id=corporate_id, person_id=person_1)
    )
    await link_repo.save(
        StaffPersonLink(id=verifier_id, corporate_id=corporate_id, person_id=person_1)
    )

    start_dto = await fixture.start.execute(
        create_start_command(fixture, dispenser_id=dispenser_id)
    )

    # 自己鑑査合格を記録（旧ポリシーでは許可）
    await fixture.verify.execute(
        VerifyDispensingCommand(
            corporate_id=str(corporate_id.value),
            dispensing_id=start_dto.id,
            verifier_id=str(verifier_id.value),
            result="passed",
        )
    )

    # 完了前にポリシーを強化（prohibit_self_verification=True）
    boundary.snapshot = DispensingPolicySnapshot(
        require_prescription_audit=False,
        prohibit_self_verification=True,
    )

    # 完了要求 -> 自己鑑査禁止ポリシー違反で409拒否
    with pytest.raises(SelfVerificationProhibitedConflictError):
        await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(corporate_id.value),
                dispensing_id=start_dto.id,
                completion_type="completed",
            )
        )
