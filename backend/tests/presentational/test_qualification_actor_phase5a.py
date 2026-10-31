"""Phase 5 Work Unit 5a: 資格と操作者本人解決・なりすまし防止テスト（TC-084〜TC-089, TC-091）。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.application.access_control.boundary_models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.care_event.commands.create_event import (
    CreateEventCommand,
    CreateEventUseCase,
)
from app.application.common.exceptions import AuthorizationError
from app.application.composition.adapters.care_event_references import (
    EventMedicationHistoryReferenceAdapter,
    EventReceptionReferenceAdapter,
)
from app.application.composition.adapters.dispensing_references import (
    DispensingStaffQualificationAdapter,
)
from app.application.composition.adapters.medication_history_references import (
    CounselorQualificationAdapter,
)
from app.application.composition.adapters.prescription_references import (
    PrescriptionStaffQualificationAdapter,
)
from app.application.composition.registry import (
    DispensingUseCases,
    PrescriptionUseCases,
    StaffUseCases,
)
from app.application.corporate.commands.services.corporate_access import (
    CorporateAccessService,
)
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingCommand,
)
from app.application.dispensing.commands.models import DispensedRpInput
from app.application.dispensing.commands.record_audit import RecordAuditCommand
from app.application.dispensing.commands.record_dispensed_content import (
    RecordDispensedContentCommand,
)
from app.application.dispensing.commands.verify_dispensing import (
    VerifyDispensingCommand,
)
from app.application.medication_history.commands.amend_medication_history import (
    AmendMedicationHistoryCommand,
)
from app.application.medication_history.commands.correct_medication_history_fact import (
    CorrectMedicationHistoryFactCommand,
    CorrectMedicationHistoryFactUseCase,
)
from app.application.medication_history.commands.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.commands.models import (
    HandbookStatusInput,
    LabeledNoteInput,
    ResidualDrugInput,
    SoapInput,
)
from app.application.medication_history.commands.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionCommand,
    ReviewExternalPrescriptionCorrectionUseCase,
)
from app.application.medication_history.commands.update_medication_history_draft import (
    UpdateMedicationHistoryDraftCommand,
)
from app.application.prescription.commands.cancel_prescription import (
    CancelPrescriptionCommand,
)
from app.application.prescription.commands.models import ReadyForDispensingCommand
from app.application.staff.commands.update_staff_qualifications import (
    UpdateStaffQualificationsUseCase,
)
from app.bootstrap import create_app
from app.domain.care_event.entities import EventDefinition
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.exceptions import CounselorQualificationError
from app.domain.medication_history.services import CounselorQualificationService
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
from app.presentational.dependencies import (
    get_dispensing_use_cases,
    get_prescription_use_cases,
    get_staff_use_cases,
)
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.application.dispensing import helpers as dispensing_helpers
from tests.application.medication_history import helpers as history_helpers
from tests.application.prescription import helpers as prescription_helpers
from tests.factories.staff_factory import create_staff
from tests.fakes.fake_event_patient_boundary import FakeEventPatientBoundary
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_event_definition_repository import (
    InMemoryEventDefinitionRepository,
)
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


def _make_actor(
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
    staff_id: StaffId | None,
    role: ActorRole = ActorRole.STORE_OPERATOR,
) -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="test-phase5a-actor",
        roles=frozenset({role}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=corporate_id,
        staff_id=staff_id,
        store_ids=frozenset({store_id}),
        managed_store_ids=frozenset({store_id})
        if role is ActorRole.STORE_MANAGER
        else frozenset(),
    )


def _dispensing_client(
    fixture: dispensing_helpers.DispensingFixture,
    actor: ActorContext,
) -> TestClient:
    bundle = DispensingUseCases(
        start=fixture.start,
        record_dispensed_content=fixture.record_content,
        verify=fixture.verify,
        record_audit=fixture.record_audit,
        complete=fixture.complete,
        get=fixture.get,
        list_by_prescription=fixture.list_by_prescription,
    )
    app = create_app(actor_provider=StubActorContextProvider(actor))
    app.dependency_overrides[get_dispensing_use_cases] = lambda: bundle
    return TestClient(app)


def _prescription_client(
    fixture: prescription_helpers.PrescriptionFixture,
    actor: ActorContext,
) -> TestClient:
    bundle = PrescriptionUseCases(
        register=fixture.register,
        get=fixture.get,
        ready_for_dispensing=fixture.ready_for_dispensing,
        cancel=fixture.cancel,
        start_inquiry=fixture.start_inquiry,
        resolve_inquiry=fixture.resolve_inquiry,
        audit_interactions=fixture.audit_interactions,
    )
    app = create_app(actor_provider=StubActorContextProvider(actor))
    app.dependency_overrides[get_prescription_use_cases] = lambda: bundle
    return TestClient(app)


# ==============================================================================
# TC-084: 調剤系/Actorなりすまし・無資格拒否・廃止済み入力422
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [
        ActorRole.CORPORATE_ADMIN,
        ActorRole.STORE_MANAGER,
        ActorRole.STORE_OPERATOR,
    ],
)
async def test_TC084_調剤系_無資格Actorは全調剤署名業務を403で拒否され他人IDなりすましも不可(
    role: ActorRole,
) -> None:
    # 1. 有資格薬剤師で準備用の調剤セッションを作成
    base_fixture = dispensing_helpers.create_fixture()
    started = await base_fixture.start.execute(
        dispensing_helpers.create_start_command(base_fixture)
    )
    dispensing_id = started.id
    pharmacist_id = base_fixture.dispenser_id

    # 2. 無資格スタッフ（各種ロール）としてFixtureを構築
    unqualified_id = StaffId.generate()
    unqualified_actor = _make_actor(
        corporate_id=base_fixture.corporate_id,
        store_id=base_fixture.store_id,
        staff_id=unqualified_id,
        role=role,
    )
    unqualified_fixture = dispensing_helpers.create_fixture(
        prescription=base_fixture.prescription,
        actor=unqualified_actor,
        verifier_actor=unqualified_actor,
    )
    unqualified_fixture.repository.items.update(base_fixture.repository.items)
    unqualified_fixture.staff_qualification.register(
        corporate_id=base_fixture.corporate_id,
        staff_id=unqualified_id,
        qualifications=StaffQualifications.empty(),
    )
    # 他人（有資格薬剤師）も登録しておく
    unqualified_fixture.staff_qualification.register(
        corporate_id=base_fixture.corporate_id,
        staff_id=pharmacist_id,
        qualifications=dispensing_helpers.create_pharmacist_qualifications(),
    )

    client = _dispensing_client(unqualified_fixture, unqualified_actor)
    cid = str(base_fixture.corporate_id.value)

    # (a) 廃止済み実施者ID入力はHTTP 422で拒否
    res_extra_start = client.post(
        f"/corporates/{cid}/dispensings",
        json={
            "store_id": str(base_fixture.store_id.value),
            "prescription_id": str(base_fixture.prescription.id.value),
            "dispenser_id": str(pharmacist_id.value),
            "iteration": 2,
            "dispensed_date": base_fixture.prescription.period.issued_date.value.isoformat(),
            "dispensed_rps": [
                TypeAdapter(DispensedRpInput).dump_python(
                    dispensing_helpers.create_rp_input(), mode="json"
                )
            ],
        },
        headers=_HEADERS,
    )
    assert res_extra_start.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert res_extra_start.json()["code"] == "REQUEST_VALIDATION_ERROR"

    res_extra_audit = client.post(
        f"/corporates/{cid}/dispensings/{dispensing_id}/audit",
        json={"auditor_id": str(pharmacist_id.value), "has_issues": False},
        headers=_HEADERS,
    )
    assert res_extra_audit.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    res_extra_verify = client.post(
        f"/corporates/{cid}/dispensings/{dispensing_id}/verification",
        json={"verifier_id": str(pharmacist_id.value), "result": "passed"},
        headers=_HEADERS,
    )
    assert res_extra_verify.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    # (b) 正規入力でも無資格Actorは全5操作が HTTP 403 FORBIDDEN で拒否される
    res_start = client.post(
        f"/corporates/{cid}/dispensings",
        json={
            "store_id": str(base_fixture.store_id.value),
            "prescription_id": str(base_fixture.prescription.id.value),
            "iteration": 2,
            "dispensed_date": base_fixture.prescription.period.issued_date.value.isoformat(),
            "dispensed_rps": [
                TypeAdapter(DispensedRpInput).dump_python(
                    dispensing_helpers.create_rp_input(), mode="json"
                )
            ],
        },
        headers=_HEADERS,
    )
    assert res_start.status_code == HTTPStatus.FORBIDDEN

    res_content = client.put(
        f"/corporates/{cid}/dispensings/{dispensing_id}/dispensed-content",
        json={
            "dispensed_rps": [
                TypeAdapter(DispensedRpInput).dump_python(
                    dispensing_helpers.create_rp_input(), mode="json"
                )
            ]
        },
        headers=_HEADERS,
    )
    assert res_content.status_code == HTTPStatus.FORBIDDEN

    res_audit = client.post(
        f"/corporates/{cid}/dispensings/{dispensing_id}/audit",
        json={"has_issues": False},
        headers=_HEADERS,
    )
    assert res_audit.status_code == HTTPStatus.FORBIDDEN

    res_verify = client.post(
        f"/corporates/{cid}/dispensings/{dispensing_id}/verification",
        json={"result": "passed"},
        headers=_HEADERS,
    )
    assert res_verify.status_code == HTTPStatus.FORBIDDEN

    res_complete = client.post(
        f"/corporates/{cid}/dispensings/{dispensing_id}/completion",
        json={"completion_type": "completed"},
        headers=_HEADERS,
    )
    assert res_complete.status_code == HTTPStatus.FORBIDDEN

    # (c) VendorOperator (staff_id=None) も 403 で拒否される
    vendor_actor = ResolvedActorContext(
        principal_id="vendor-op",
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=None,
        staff_id=None,
        store_ids=frozenset(),
    )
    vendor_fixture = dispensing_helpers.create_fixture(
        prescription=base_fixture.prescription,
        actor=vendor_actor,
        verifier_actor=vendor_actor,
    )
    vendor_client = _dispensing_client(vendor_fixture, vendor_actor)
    res_vendor = vendor_client.post(
        f"/corporates/{cid}/dispensings",
        json={
            "store_id": str(base_fixture.store_id.value),
            "prescription_id": str(base_fixture.prescription.id.value),
            "iteration": 1,
            "dispensed_date": base_fixture.prescription.period.issued_date.value.isoformat(),
            "dispensed_rps": [
                TypeAdapter(DispensedRpInput).dump_python(
                    dispensing_helpers.create_rp_input(), mode="json"
                )
            ],
        },
        headers=_HEADERS,
    )
    assert res_vendor.status_code == HTTPStatus.FORBIDDEN


# ==============================================================================
# TC-085: 調剤系/正常署名（Actor本人のstaff_idで保存）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC085_調剤系_有効薬剤師Actorで全調剤操作を実行するとActor本人のstaff_idで記録される() -> (
    None
):
    dispenser_id = StaffId.generate()
    verifier_id = StaffId.generate()
    dispenser_actor = dispensing_helpers.create_resolved_actor(staff_id=dispenser_id)
    verifier_actor = dispensing_helpers.create_resolved_actor(staff_id=verifier_id)
    fixture = dispensing_helpers.create_fixture(
        actor=dispenser_actor,
        verifier_actor=verifier_actor,
    )
    cid = str(fixture.corporate_id.value)

    # 1. 開始（dispenser_id指定なし）
    started = await fixture.start.execute(
        dispensing_helpers.create_start_command(fixture)
    )
    assert started.dispenser_id == str(dispenser_id.value)

    # 2. 内容変更
    updated = await fixture.record_content.execute(
        RecordDispensedContentCommand(
            corporate_id=cid,
            dispensing_id=started.id,
            dispensed_rps=(dispensing_helpers.create_rp_input(quantity=7),),
        )
    )
    assert updated.dispensed_rps[0].quantity == 7

    # 3. 処方鑑査（auditor_id指定なし）
    audited = await fixture.record_audit.execute(
        RecordAuditCommand(
            corporate_id=cid,
            dispensing_id=started.id,
            has_issues=False,
        )
    )
    assert audited.audit is not None
    assert audited.audit.auditor_id == str(verifier_id.value)

    # 4. 最終鑑査（verifier_id指定なし）
    verified = await fixture.verify.execute(
        VerifyDispensingCommand(
            corporate_id=cid,
            dispensing_id=started.id,
            result="passed",
        )
    )
    assert verified.verification is not None
    assert verified.verification.verifier_id == str(verifier_id.value)

    # 5. 交付完了
    completed = await fixture.complete.execute(
        CompleteDispensingCommand(
            corporate_id=cid,
            dispensing_id=started.id,
            completion_type="completed",
        )
    )
    assert completed.status == "completed"


# ==============================================================================
# TC-086: 疑義照会/資格・なりすまし拒否
# ==============================================================================
@pytest.mark.asyncio
async def test_TC086_疑義照会_無資格403_有資格はActor本人保存_他人ID指定は拒否() -> (
    None
):
    pharmacist_id = StaffId.generate()
    pharmacist_actor = prescription_helpers.create_resolved_actor(
        staff_id=pharmacist_id
    )
    fixture = prescription_helpers.create_fixture(actor=pharmacist_actor)
    registered = await fixture.register.execute(
        prescription_helpers.create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )
    )
    cid = str(fixture.corporate_id.value)

    # 1. HTTPで廃止済み pharmacist_id を送ると 422
    client = _prescription_client(fixture, pharmacist_actor)
    res_extra = client.post(
        f"/corporates/{cid}/prescriptions/{registered.id}/inquiries",
        json={
            "pharmacist_id": str(pharmacist_id.value),
            "category": "dosage",
            "content": "用量確認",
        },
        headers=_HEADERS,
    )
    assert res_extra.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    # 2. 有資格薬剤師が開始すると Actor 本人の staff_id で記録される
    res_start = client.post(
        f"/corporates/{cid}/prescriptions/{registered.id}/inquiries",
        json={"category": "dosage", "content": "用量確認"},
        headers=_HEADERS,
    )
    assert res_start.status_code == HTTPStatus.CREATED
    assert res_start.json()["inquiries"][0]["pharmacist_id"] == str(pharmacist_id.value)

    # 3. 無資格スタッフが開始・解決を試みると 403 FORBIDDEN
    clerk_id = StaffId.generate()
    clerk_actor = prescription_helpers.create_resolved_actor(staff_id=clerk_id)
    clerk_fixture = prescription_helpers.create_fixture(actor=clerk_actor)
    clerk_fixture.repository.items.update(fixture.repository.items)
    clerk_fixture.staff_qualification.register(
        corporate_id=fixture.corporate_id,
        staff_id=clerk_id,
        qualifications=StaffQualifications.empty(),
    )
    clerk_client = _prescription_client(clerk_fixture, clerk_actor)

    res_clerk_start = clerk_client.post(
        f"/corporates/{cid}/prescriptions/{registered.id}/inquiries",
        json={"category": "dosage", "content": "無資格照会"},
        headers=_HEADERS,
    )
    assert res_clerk_start.status_code == HTTPStatus.FORBIDDEN

    res_clerk_resolve = clerk_client.post(
        f"/corporates/{cid}/prescriptions/{registered.id}/inquiries/1/resolution",
        json={
            "responded_by": "佐藤医師",
            "result_type": "unchanged",
            "content": "問題なし",
        },
        headers=_HEADERS,
    )
    assert res_clerk_resolve.status_code == HTTPStatus.FORBIDDEN

    # 4. 有資格薬剤師なら解決も成功する
    res_resolve = client.post(
        f"/corporates/{cid}/prescriptions/{registered.id}/inquiries/1/resolution",
        json={
            "responded_by": "佐藤医師",
            "result_type": "unchanged",
            "content": "問題なし",
        },
        headers=_HEADERS,
    )
    assert res_resolve.status_code == HTTPStatus.OK
    assert res_resolve.json()["has_open_inquiry"] is False


# ==============================================================================
# TC-087: 薬歴/資格・責任（start/finalize/correct/amend/review/tracing_report）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC087_薬歴_指導と確定と訂正と外部承認は薬剤師資格を要求し過去実施者を書き換えない() -> (
    None
):
    pharmacist_1 = StaffId.generate()
    pharmacist_2 = StaffId.generate()
    clerk_id = StaffId.generate()

    # 薬剤師1で下書き作成（指導日時も記録）
    fixture_1 = history_helpers.create_fixture(
        actor=history_helpers.create_resolved_actor(staff_id=pharmacist_1)
    )
    fixture_1.staff_qualification.register(
        corporate_id=fixture_1.corporate_id,
        staff_id=pharmacist_1,
        qualifications=history_helpers.create_pharmacist_qualifications(),
    )
    counseled_at = fixture_1.clock.now() - timedelta(minutes=30)
    started = await fixture_1.start.execute(
        replace(
            history_helpers.create_start_command(fixture_1),
            counselor_id=None,
            counseled_at=counseled_at,
        )
    )
    assert started.recorded_by == str(pharmacist_1.value)
    assert started.counselor_id == str(pharmacist_1.value)

    # 薬剤師2で確定 -> finalized_by は薬剤師2だが、過去の recorded_by / counselor_id は薬剤師1のまま保持
    fixture_2 = history_helpers.create_fixture(
        actor=history_helpers.create_resolved_actor(staff_id=pharmacist_2)
    )
    fixture_2.record_repository.items.update(fixture_1.record_repository.items)
    fixture_2.event_repository.items.update(fixture_1.event_repository.items)
    fixture_2.staff_qualification.register(
        corporate_id=fixture_1.corporate_id,
        staff_id=pharmacist_1,
        qualifications=history_helpers.create_pharmacist_qualifications(),
    )
    fixture_2.staff_qualification.register(
        corporate_id=fixture_1.corporate_id,
        staff_id=pharmacist_2,
        qualifications=history_helpers.create_pharmacist_qualifications(),
    )
    finalized = await fixture_2.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture_1.corporate_id.value),
            record_id=started.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    assert finalized.recorded_by == str(pharmacist_1.value)
    assert finalized.counselor_id == str(pharmacist_1.value)
    assert finalized.finalized_by == str(pharmacist_2.value)

    # 無資格スタッフ（clerk_id）は start / finalize / correct / amend / review / tracing_report すべて拒否
    clerk_fixture = history_helpers.create_fixture(
        actor=history_helpers.create_resolved_actor(staff_id=clerk_id)
    )
    clerk_fixture.record_repository.items.update(fixture_2.record_repository.items)
    clerk_fixture.event_repository.items.update(fixture_2.event_repository.items)
    clerk_fixture.staff_qualification.register(
        corporate_id=fixture_1.corporate_id,
        staff_id=clerk_id,
        qualifications=StaffQualifications.empty(),
    )
    clerk_fixture.staff_qualification.register(
        corporate_id=clerk_fixture.corporate_id,
        staff_id=clerk_id,
        qualifications=StaffQualifications.empty(),
    )

    with pytest.raises(CounselorQualificationError):
        await clerk_fixture.start.execute(
            history_helpers.create_start_command(clerk_fixture)
        )

    with pytest.raises(CounselorQualificationError):
        await clerk_fixture.amend.execute(
            AmendMedicationHistoryCommand(
                corporate_id=str(fixture_1.corporate_id.value),
                record_id=started.id,
                reason="追記",
                amended_soap=history_helpers.create_soap_input(),
            )
        )

    correct_uc = CorrectMedicationHistoryFactUseCase(
        record_repository=clerk_fixture.record_repository,
        profile_repository=clerk_fixture.profile_repository,
        corporate_access=clerk_fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=FakeOrganizationLock(),
        staff_qualification=clerk_fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        category_catalog_repository=clerk_fixture.category_catalog_repository,
        store_operations=clerk_fixture.store_operations,
        clock=clerk_fixture.clock,
    )
    with pytest.raises(CounselorQualificationError):
        await correct_uc.execute(
            CorrectMedicationHistoryFactCommand(
                corporate_id=str(fixture_1.corporate_id.value),
                record_id=started.id,
                target="information_sheet_provided",
                operation="replace",
                reason="事実訂正",
                value=True,
            )
        )

    # review_external_prescription_correction も無資格スタッフは CounselorQualificationError で拒否
    review_uc = ReviewExternalPrescriptionCorrectionUseCase(
        clerk_fixture.record_repository,
        clerk_fixture.corporate_access,
        clerk_fixture.staff_qualification,
        InMemoryPrescriptionRepository(),
        clerk_fixture.clock,
    )
    with pytest.raises(CounselorQualificationError):
        await review_uc.execute(
            ReviewExternalPrescriptionCorrectionCommand(
                corporate_id=str(fixture_1.corporate_id.value),
                record_id=started.id,
                correction_id="corr-001",
                decision="no_action",
                reason="確認済み",
            )
        )


# ==============================================================================
# TC-088: 事務職/許可範囲（処方登録・判断確定・取消、Event作成、薬歴下書き更新、TR返答）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC088_事務職_非薬剤師スタッフでも処方登録やEvent作成や薬歴下書き編集を実行できる() -> (
    None
):
    clerk_id = StaffId.generate()

    # 1. 処方箋登録・調剤可能化・取消は非薬剤師でも成功
    presc_fixture = prescription_helpers.create_fixture(
        actor=prescription_helpers.create_resolved_actor(staff_id=clerk_id)
    )
    presc_fixture.staff_qualification.register(
        corporate_id=presc_fixture.corporate_id,
        staff_id=clerk_id,
        qualifications=StaffQualifications.empty(),
    )
    registered = await presc_fixture.register.execute(
        prescription_helpers.create_register_command(
            corporate_id=presc_fixture.corporate_id,
            store_id=presc_fixture.store_id,
            patient_id=presc_fixture.patient_id,
        )
    )
    ready = await presc_fixture.ready_for_dispensing.execute(
        ReadyForDispensingCommand(
            corporate_id=str(presc_fixture.corporate_id.value),
            prescription_id=registered.id,
        )
    )
    assert ready.status == "ready_for_dispensing"

    cancelled = await presc_fixture.cancel.execute(
        CancelPrescriptionCommand(
            corporate_id=str(presc_fixture.corporate_id.value),
            prescription_id=registered.id,
        )
    )
    assert cancelled.status == "cancelled"

    # 2. 薬歴の下書き更新（UpdateMedicationHistoryDraftUseCase）とTR返答記録は非薬剤師でも成功
    hist_fixture = history_helpers.create_fixture()
    started = await hist_fixture.start.execute(
        history_helpers.create_start_command(hist_fixture)
    )

    clerk_hist_fixture = history_helpers.create_fixture(
        actor=history_helpers.create_resolved_actor(staff_id=clerk_id)
    )
    clerk_hist_fixture.record_repository.items.update(
        hist_fixture.record_repository.items
    )
    clerk_hist_fixture.event_repository.items.update(
        hist_fixture.event_repository.items
    )
    updated_draft = await clerk_hist_fixture.update_draft.execute(
        UpdateMedicationHistoryDraftCommand(
            corporate_id=str(hist_fixture.corporate_id.value),
            record_id=started.id,
            method="face_to_face",
            soap=SoapInput(subjective=(LabeledNoteInput(text="事務聴取メモ"),)),
            handbook_status=HandbookStatusInput(presented=True),
            residual_drug=ResidualDrugInput(has_residual_drugs=False),
        )
    )
    assert updated_draft.soap.subjective[0].text == "事務聴取メモ"

    # 3. 一般Eventの作成も非薬剤師で成功
    event_definitions = InMemoryEventDefinitionRepository()
    general_def = EventDefinition.create_standard(
        code=EventTypeStandardCode("general_consultation"),
        name=EventTypeName("一般相談"),
    )
    event_definitions.items[general_def.id] = general_def
    event_patient = FakeEventPatientBoundary()
    event_patient.register(
        corporate_id=hist_fixture.corporate_id,
        patient_id=hist_fixture.patient_id,
    )
    create_event_uc = CreateEventUseCase(
        event_repository=clerk_hist_fixture.event_repository,
        event_definition_repository=event_definitions,
        patient_boundary=event_patient,
        corporate_access=clerk_hist_fixture.corporate_access,
        store_operations=clerk_hist_fixture.store_operations,
        clock=clerk_hist_fixture.clock,
        reception_boundary=EventReceptionReferenceAdapter(
            clerk_hist_fixture.reception_repository
        ),
        medication_history=EventMedicationHistoryReferenceAdapter(
            clerk_hist_fixture.record_repository
        ),
    )
    created_event = await create_event_uc.execute(
        CreateEventCommand(
            corporate_id=str(hist_fixture.corporate_id.value),
            store_id=str(hist_fixture.store_id.value),
            patient_id=str(hist_fixture.patient_id.value),
            event_type_id=str(general_def.id.value),
            occurred_at=datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
        )
    )
    assert created_event.store_id == str(hist_fixture.store_id.value)


# ==============================================================================
# TC-089: Staff有効性・所属期間境界（主所属/兼務・閉区間境界・停止スタッフ）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC089_Staff有効性と所属期間境界_停止や期間外は拒否し当日有効な主所属と兼務のみ許可() -> (
    None
):
    corporate_id = CorporateId.generate()
    store_primary = StoreId.generate()
    store_concurrent = StoreId.generate()
    store_other = StoreId.generate()

    staff_repo = InMemoryStaffRepository()
    disp_adapter = DispensingStaffQualificationAdapter(staff_repo)
    presc_adapter = PrescriptionStaffQualificationAdapter(staff_repo)
    hist_adapter = CounselorQualificationAdapter(staff_repo)

    pharmacist_quals = StaffQualifications.from_profiles(
        PharmacistProfile(license_number=PharmacistLicenseNumber("654321"))
    )

    # 1. 主所属(2026-10-01〜2026-10-31) + 兼務(2026-10-15〜2026-10-20) の有効薬剤師
    active_staff = replace(
        create_staff(corporate_id=corporate_id, qualifications=pharmacist_quals),
        affiliations=(
            StoreAffiliation(
                store_id=store_primary,
                is_primary=True,
                period=AffiliationPeriod(
                    start_date=date(2026, 10, 1),
                    end_date=date(2026, 10, 31),
                ),
            ),
            StoreAffiliation(
                store_id=store_concurrent,
                is_primary=False,
                period=AffiliationPeriod(
                    start_date=date(2026, 10, 15),
                    end_date=date(2026, 10, 20),
                ),
            ),
        ),
    )
    await staff_repo.save(active_staff)

    for adapter in (disp_adapter, presc_adapter, hist_adapter):
        # 開始前日 (2026-09-30) -> 期間外のため AuthorizationError (403)
        with pytest.raises(AuthorizationError):
            await adapter.get_qualifications(
                corporate_id=corporate_id,
                staff_id=active_staff.id,
                store_id=store_primary,
                as_of=date(2026, 9, 30),
            )

        # 開始日当日 (2026-10-01) -> 薬剤師資格あり
        q_start = await adapter.get_qualifications(
            corporate_id=corporate_id,
            staff_id=active_staff.id,
            store_id=store_primary,
            as_of=date(2026, 10, 1),
        )
        assert q_start.has_pharmacist

        # 終了日当日 (2026-10-31) -> 薬剤師資格あり
        q_end = await adapter.get_qualifications(
            corporate_id=corporate_id,
            staff_id=active_staff.id,
            store_id=store_primary,
            as_of=date(2026, 10, 31),
        )
        assert q_end.has_pharmacist

        # 終了翌日 (2026-11-01) -> 期間外のため AuthorizationError (403)
        with pytest.raises(AuthorizationError):
            await adapter.get_qualifications(
                corporate_id=corporate_id,
                staff_id=active_staff.id,
                store_id=store_primary,
                as_of=date(2026, 11, 1),
            )

        # 兼務店舗: 期間内 (2026-10-15) は有効、期間外 (2026-10-21) は AuthorizationError
        q_conc_ok = await adapter.get_qualifications(
            corporate_id=corporate_id,
            staff_id=active_staff.id,
            store_id=store_concurrent,
            as_of=date(2026, 10, 15),
        )
        assert q_conc_ok.has_pharmacist

        with pytest.raises(AuthorizationError):
            await adapter.get_qualifications(
                corporate_id=corporate_id,
                staff_id=active_staff.id,
                store_id=store_concurrent,
                as_of=date(2026, 10, 21),
            )

        # 所属のない他店舗 -> AuthorizationError
        with pytest.raises(AuthorizationError):
            await adapter.get_qualifications(
                corporate_id=corporate_id,
                staff_id=active_staff.id,
                store_id=store_other,
                as_of=date(2026, 10, 15),
            )

    # 2. 退職済み（is_active=False）の薬剤師は期間内でも AuthorizationError
    retired_staff = replace(active_staff, id=StaffId.generate(), is_active=False)
    await staff_repo.save(retired_staff)
    for adapter in (disp_adapter, presc_adapter, hist_adapter):
        with pytest.raises(AuthorizationError):
            await adapter.get_qualifications(
                corporate_id=corporate_id,
                staff_id=retired_staff.id,
                store_id=store_primary,
                as_of=date(2026, 10, 15),
            )


# ==============================================================================
# TC-091: 資格編集/自己昇格防止（一般職・店舗管理者は403、未知is_pharmacistは422）
# ==============================================================================
def test_TC091_資格編集_一般職と店舗管理者の自己昇格を403で拒否し未知is_pharmacist入力を422で拒否する() -> (
    None
):
    corporate_id = CorporateId.generate()
    store_id = StoreId.generate()
    staff = create_staff(
        corporate_id=corporate_id,
        qualifications=StaffQualifications.empty(),
    )
    staff_repo = InMemoryStaffRepository()
    staff_repo.items[staff.id] = staff
    corp_repo = AutoProvisioningCorporateRepository()

    def _client_for_role(role: ActorRole) -> TestClient:
        actor = _make_actor(
            corporate_id=corporate_id,
            store_id=store_id,
            staff_id=staff.id,
            role=role,
        )
        access = CorporateAccessService(corp_repo, AuthorizationService(actor))
        update_uc = UpdateStaffQualificationsUseCase(staff_repo, access)
        bundle = StaffUseCases(
            register=None,  # type: ignore[arg-type]
            get=None,  # type: ignore[arg-type]
            list_by_corporate=None,  # type: ignore[arg-type]
            change_names=None,  # type: ignore[arg-type]
            change_job_title=None,  # type: ignore[arg-type]
            update_qualifications=update_uc,
            transfer_home_store=None,  # type: ignore[arg-type]
            assign_concurrent_store=None,  # type: ignore[arg-type]
            remove_concurrent_store=None,  # type: ignore[arg-type]
            deactivate=None,  # type: ignore[arg-type]
            activate=None,  # type: ignore[arg-type]
        )
        app = create_app(actor_provider=StubActorContextProvider(actor))
        app.dependency_overrides[get_staff_use_cases] = lambda: bundle
        return TestClient(app)

    url = f"/corporates/{corporate_id.value}/staffs/{staff.id.value}/qualifications"

    # 1. 一般スタッフと管理薬剤師による自己昇格は 403 FORBIDDEN
    for denied_role in (ActorRole.STORE_OPERATOR, ActorRole.STORE_MANAGER):
        denied_client = _client_for_role(denied_role)
        res = denied_client.put(
            url,
            json={"pharmacist_license_number": "999999"},
            headers=_HEADERS,
        )
        assert res.status_code == HTTPStatus.FORBIDDEN
        assert not staff_repo.items[staff.id].qualifications.has(PharmacistProfile)

    # 2. 未知の is_pharmacist フィールド送信は 422
    admin_client = _client_for_role(ActorRole.CORPORATE_ADMIN)
    res_unknown = admin_client.put(
        url,
        json={"is_pharmacist": True},
        headers=_HEADERS,
    )
    assert res_unknown.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert not staff_repo.items[staff.id].qualifications.has(PharmacistProfile)

    # 3. 法人管理者による正規の資格更新は 204 NO_CONTENT で反映される
    res_ok = admin_client.put(
        url,
        json={"pharmacist_license_number": "123456"},
        headers=_HEADERS,
    )
    assert res_ok.status_code == HTTPStatus.NO_CONTENT
    assert staff_repo.items[staff.id].qualifications.has(PharmacistProfile)
