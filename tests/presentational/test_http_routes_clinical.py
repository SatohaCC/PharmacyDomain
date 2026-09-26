"""処方箋・調剤・薬歴のHTTPルートの振る舞い。

この3つは参照Boundaryを多数必要とするため、``conftest.py`` の土台には載せず、
Application層テストの Fixture をそのまま束へ入れ替える。入力は入れ子が深いので、
本文もルータのリクエストモデルから ``model_dump(mode="json")`` で作る。手書きの
JSONを置くと、Application層の項目が増えたときにテストだけ古いまま緑になる。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.application.access_control.policy import AuthorizationService
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.medication_history.get_medication_history_view import (
    CurrentPatientProfileBoundary,
    GetMedicationHistoryViewUseCase,
    MedicationHistoryPatientProfileDto,
)
from app.application.medication_history.inputs import (
    CategorizedNoteInput,
    HandbookStatusInput,
    LabeledNoteInput,
    ResidualDrugInput,
    SoapInput,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import StatutoryDispensingRecordItem
from app.domain.medication_history.value_objects import SoapRecord
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import (
    InquiryNumber,
    InquiryResultType,
)
from app.domain.reception.primitives import ReceptionFingerprint, ReceptionId
from app.domain.reception.reception import (
    Reception,
    ReceptionBillingAddition,
    ReceptionSourceData,
)
from app.domain.staff.primitives import StaffId
from app.infrastructure.di.bundles.clinical import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
)
from app.presentational.app_factory import create_app
from app.presentational.dependencies import (
    get_dispensing_use_cases,
    get_medication_history_use_cases,
    get_prescription_use_cases,
)
from app.presentational.routers.dispensing import StartDispensingRequest
from app.presentational.routers.medication_history import (
    AddFollowUpRequest,
    FinalizeMedicationHistoryRequest,
    RecordTracingReportRequest,
    RecordTracingReportResponseRequest,
    StartMedicationHistoryRequest,
    UpdateMedicationHistoryDraftRequest,
)
from app.presentational.routers.prescription import RegisterPrescriptionRequest
from tests.application.dispensing import helpers as dispensing_helpers
from tests.application.medication_history import helpers as history_helpers
from tests.application.medication_history.helpers import (
    create_pharmacist_qualifications,
)
from tests.application.prescription import helpers as prescription_helpers
from tests.factories.medication_history_factory import (
    create_note,
    create_nsips_draft_record,
)
from tests.factories.prescription_factory import create_response, start_inquiry
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.presentational.helpers import vendor_admin

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


def _client(overrides: dict[Any, Any]) -> Iterator[TestClient]:
    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides.update(overrides)
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- 処方箋 -----------------------------------------------------------------


@pytest.fixture
def prescription_fixture() -> prescription_helpers.PrescriptionFixture:
    return prescription_helpers.create_fixture()


@pytest.fixture
def prescription_client(
    prescription_fixture: prescription_helpers.PrescriptionFixture,
) -> Iterator[TestClient]:
    bundle = PrescriptionUseCases(
        register=prescription_fixture.register,
        get=prescription_fixture.get,
        ready_for_dispensing=prescription_fixture.ready_for_dispensing,
        cancel=prescription_fixture.cancel,
        start_inquiry=prescription_fixture.start_inquiry,
        resolve_inquiry=prescription_fixture.resolve_inquiry,
        audit_interactions=prescription_fixture.audit_interactions,
    )
    yield from _client({get_prescription_use_cases: lambda: bundle})


def _register_prescription_body(
    fixture: prescription_helpers.PrescriptionFixture,
) -> dict[str, Any]:
    """Application層テストと同じ入力を、そのままJSON本文にする。"""
    command = prescription_helpers.create_register_command(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )
    return RegisterPrescriptionRequest(
        store_id=command.store_id,
        patient_id=command.patient_id,
        source_type=command.source_type,
        document_number=command.document_number,
        issued_date=command.issued_date,
        medical_institution=command.medical_institution,
        department=command.department,
        prescriber=command.prescriber,
        rps=list(command.rps),
        valid_to=command.valid_to,
        management_info=command.management_info,
        coverage_selection_record_id=command.coverage_selection_record_id,
    ).model_dump(mode="json")


def test_処方箋を登録して_剤の入れ子ごと取得できる(
    prescription_client: TestClient,
    prescription_fixture: prescription_helpers.PrescriptionFixture,
) -> None:
    # Arrange
    corporate_id = str(prescription_fixture.corporate_id.value)
    body = _register_prescription_body(prescription_fixture)

    # Act
    registered = prescription_client.post(
        f"/corporates/{corporate_id}/prescriptions", json=body, headers=_HEADERS
    )
    detail = prescription_client.get(
        f"/corporates/{corporate_id}/prescriptions/{registered.json()['id']}",
        headers=_HEADERS,
    )

    # Assert: 剤→薬品明細の2段の入れ子が、並び順の規約ではなく構造のまま返る。
    assert registered.status_code == HTTPStatus.CREATED, registered.text
    assert detail.status_code == HTTPStatus.OK
    rps = detail.json()["rps"]
    assert [rp["rp_number"] for rp in rps] == [1]
    assert [medicine["line_number"] for medicine in rps[0]["medicines"]] == [1]
    assert rps[0]["medicines"][0]["amount"] == "3"


def test_未回答の疑義照会が残ると_調剤可能にできない(
    prescription_client: TestClient,
    prescription_fixture: prescription_helpers.PrescriptionFixture,
) -> None:
    # Arrange
    corporate_id = str(prescription_fixture.corporate_id.value)
    prescription_id = prescription_client.post(
        f"/corporates/{corporate_id}/prescriptions",
        json=_register_prescription_body(prescription_fixture),
        headers=_HEADERS,
    ).json()["id"]
    base = f"/corporates/{corporate_id}/prescriptions/{prescription_id}"

    # Act
    inquired = prescription_client.post(
        f"{base}/inquiries",
        json={
            "pharmacist_id": str(prescription_fixture.pharmacist_id.value),
            "category": "dosage",
            "content": "用量の確認をお願いします。",
        },
        headers=_HEADERS,
    )
    blocked = prescription_client.post(f"{base}/readiness", headers=_HEADERS)

    # Assert
    assert inquired.status_code == HTTPStatus.CREATED, inquired.text
    assert inquired.json()["has_open_inquiry"] is True
    assert blocked.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert blocked.json()["code"]


def test_疑義照会に回答すると_調剤可能にできる(
    prescription_client: TestClient,
    prescription_fixture: prescription_helpers.PrescriptionFixture,
) -> None:
    # Arrange
    corporate_id = str(prescription_fixture.corporate_id.value)
    prescription_id = prescription_client.post(
        f"/corporates/{corporate_id}/prescriptions",
        json=_register_prescription_body(prescription_fixture),
        headers=_HEADERS,
    ).json()["id"]
    base = f"/corporates/{corporate_id}/prescriptions/{prescription_id}"
    prescription_client.post(
        f"{base}/inquiries",
        json={
            "pharmacist_id": str(prescription_fixture.pharmacist_id.value),
            "category": "dosage",
            "content": "用量の確認をお願いします。",
        },
        headers=_HEADERS,
    )

    # Act
    resolved = prescription_client.post(
        f"{base}/inquiries/1/resolution",
        json={
            "responded_by": "田中医師",
            "result_type": "unchanged",
            "content": "記載どおりで問題ありません。",
        },
        headers=_HEADERS,
    )
    ready = prescription_client.post(f"{base}/readiness", headers=_HEADERS)

    # Assert
    assert resolved.status_code == HTTPStatus.OK, resolved.text
    assert resolved.json()["has_open_inquiry"] is False
    assert ready.status_code == HTTPStatus.OK, ready.text
    assert ready.json()["status"] == "ready_for_dispensing"


def test_処方薬相互作用鑑査で全組み合わせが取得できる(
    prescription_client: TestClient,
    prescription_fixture: prescription_helpers.PrescriptionFixture,
) -> None:
    """TC-11: 複数YJコードをPOSTすると全組み合わせの相互作用鑑査結果が返る。"""
    corporate_id = str(prescription_fixture.corporate_id.value)
    response = prescription_client.post(
        f"/corporates/{corporate_id}/prescriptions/audit-interactions",
        json={"yj_codes": ["1179041F1025", "2149001F1020", "3339001F1023"]},
        headers=_HEADERS,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["total_combinations"] == 3
    assert len(data["pairs"]) == 3


# --- 調剤 -------------------------------------------------------------------


@pytest.fixture
def dispensing_fixture() -> dispensing_helpers.DispensingFixture:
    return dispensing_helpers.create_fixture()


@pytest.fixture
def dispensing_client(
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> Iterator[TestClient]:
    bundle = DispensingUseCases(
        start=dispensing_fixture.start,
        record_dispensed_content=dispensing_fixture.record_content,
        verify=dispensing_fixture.verify,
        record_audit=dispensing_fixture.record_audit,
        complete=dispensing_fixture.complete,
        get=dispensing_fixture.get,
        list_by_prescription=dispensing_fixture.list_by_prescription,
    )
    yield from _client({get_dispensing_use_cases: lambda: bundle})


def _start_dispensing_body(
    fixture: dispensing_helpers.DispensingFixture,
) -> dict[str, Any]:
    return StartDispensingRequest(
        store_id=str(fixture.store_id.value),
        prescription_id=str(fixture.prescription.id.value),
        dispenser_id=str(fixture.dispenser_id.value),
        iteration=1,
        dispensed_date=fixture.prescription.period.issued_date.value,
        dispensed_rps=[dispensing_helpers.create_rp_input()],
    ).model_dump(mode="json")


def test_調剤を開始して_鑑査と完了まで進められる(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    # Arrange
    corporate_id = str(dispensing_fixture.corporate_id.value)
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=_start_dispensing_body(dispensing_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    base = f"/corporates/{corporate_id}/dispensings/{started.json()['id']}"

    # Act
    verified = dispensing_client.post(
        f"{base}/verification",
        json={
            "verifier_id": str(dispensing_fixture.verifier_id.value),
            "result": "passed",
        },
        headers=_HEADERS,
    )
    completed = dispensing_client.post(
        f"{base}/completion", json={"completion_type": "completed"}, headers=_HEADERS
    )

    # Assert
    assert verified.status_code == HTTPStatus.OK, verified.text
    assert verified.json()["verification"]["result"] == "passed"
    assert completed.status_code == HTTPStatus.OK, completed.text
    assert completed.json()["status"] == "completed"


def test_分割調剤を開始すると_今回回数と合計分割回数が返る(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    corporate_id = str(dispensing_fixture.corporate_id.value)
    body = _start_dispensing_body(dispensing_fixture)
    body["split_reason"] = "long_term_storage"
    body["total_split_count"] = 2
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=body,
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    res = started.json()
    assert res["iteration"] == 1
    assert res["split_reason"] == "long_term_storage"
    assert res["total_split_count"] == 2


def test_処方箋ごとの調剤一覧が引ける(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    # Arrange
    corporate_id = str(dispensing_fixture.corporate_id.value)
    prescription_id = str(dispensing_fixture.prescription.id.value)
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=_start_dispensing_body(dispensing_fixture),
        headers=_HEADERS,
    )

    # Act
    listed = dispensing_client.get(
        f"/corporates/{corporate_id}/prescriptions/{prescription_id}/dispensings",
        headers=_HEADERS,
    )

    # Assert
    assert listed.status_code == HTTPStatus.OK
    assert [item["id"] for item in listed.json()] == [started.json()["id"]]


def test_鑑査を通していない調剤は_完了できない(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    # Arrange
    corporate_id = str(dispensing_fixture.corporate_id.value)
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=_start_dispensing_body(dispensing_fixture),
        headers=_HEADERS,
    )
    base = f"/corporates/{corporate_id}/dispensings/{started.json()['id']}"

    # Act
    completed = dispensing_client.post(
        f"{base}/completion", json={"completion_type": "completed"}, headers=_HEADERS
    )

    # Assert
    assert completed.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert completed.json()["code"]


def test_疑義照会処方変更を含む調剤をHTTP経由で開始できる(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    """TC-HTTP-01: POST .../dispensings で inquiry_modified と inquiry_number を送信すると 201 CREATED。"""
    # Arrange
    corporate_id = str(dispensing_fixture.corporate_id.value)
    modified_prescription = (
        start_inquiry(dispensing_fixture.prescription)
        .resolve_inquiry(
            inquiry_number=InquiryNumber(1),
            response=create_response(result_type=InquiryResultType.MODIFIED),
        )
        .ready_for_dispensing()
    )
    dispensing_fixture.prescription_source.register(modified_prescription)

    body = StartDispensingRequest(
        store_id=str(dispensing_fixture.store_id.value),
        prescription_id=str(modified_prescription.id.value),
        dispenser_id=str(dispensing_fixture.dispenser_id.value),
        iteration=1,
        dispensed_date=modified_prescription.period.issued_date.value,
        dispensed_rps=[
            dispensing_helpers.create_rp_input(
                medicines=(
                    dispensing_helpers.create_inquiry_substituted_medicine_input(
                        inquiry_number=1
                    ),
                )
            )
        ],
    ).model_dump(mode="json")

    # Act
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert started.status_code == HTTPStatus.CREATED, started.text
    sub = started.json()["dispensed_rps"][0]["medicines"][0]["substitution"]
    assert sub is not None
    assert sub["category"] == "inquiry_modified"
    assert sub["inquiry_number"] == 1


def test_実在しない疑義照会連番を指定すると422が返る(
    dispensing_client: TestClient,
    dispensing_fixture: dispensing_helpers.DispensingFixture,
) -> None:
    """TC-HTTP-02: inquiry_number が実在しない照会連番の場合 422 UNPROCESSABLE_CONTENT。"""
    # Arrange
    corporate_id = str(dispensing_fixture.corporate_id.value)
    body = StartDispensingRequest(
        store_id=str(dispensing_fixture.store_id.value),
        prescription_id=str(dispensing_fixture.prescription.id.value),
        dispenser_id=str(dispensing_fixture.dispenser_id.value),
        iteration=1,
        dispensed_date=dispensing_fixture.prescription.period.issued_date.value,
        dispensed_rps=[
            dispensing_helpers.create_rp_input(
                medicines=(
                    dispensing_helpers.create_inquiry_substituted_medicine_input(
                        inquiry_number=999
                    ),
                )
            )
        ],
    ).model_dump(mode="json")

    # Act
    started = dispensing_client.post(
        f"/corporates/{corporate_id}/dispensings",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert started.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, started.text


# --- 薬歴 -------------------------------------------------------------------


@pytest.fixture
def history_fixture() -> history_helpers.MedicationHistoryFixture:
    return history_helpers.create_fixture()


@pytest.fixture
def history_client(
    history_fixture: history_helpers.MedicationHistoryFixture,
    current_patient_profile_reader: _HttpCurrentPatientProfileReader,
) -> Iterator[TestClient]:
    view_use_case = GetMedicationHistoryViewUseCase(
        history_fixture.record_repository,
        current_patient_profile_reader,
        CorporateAccessService(
            history_fixture.corporate_repository,
            AuthorizationService(vendor_admin()),
        ),
    )
    bundle = MedicationHistoryUseCases(
        start=history_fixture.start,
        update_draft=history_fixture.update_draft,
        finalize=history_fixture.finalize,
        amend=history_fixture.amend,
        get=history_fixture.get,
        list_by_patient=history_fixture.list_by_patient,
        get_medical_profile=history_fixture.get_profile,
        rebuild_medical_profile=history_fixture.rebuild_profile,
        verify_statutory_record=history_fixture.verify_statutory_record,
        get_category_catalog=history_fixture.get_category_catalog,
        update_category_catalog=history_fixture.update_category_catalog,
        add_follow_up=history_fixture.add_follow_up,
        record_tracing_report=history_fixture.record_tracing_report,
        record_tracing_report_response=history_fixture.record_tracing_report_response,
        get_view=view_use_case,
    )
    app = create_app(actor_provider=StubActorContextProvider(history_fixture.actor))
    app.dependency_overrides.update({get_medication_history_use_cases: lambda: bundle})
    yield TestClient(app)
    app.dependency_overrides.clear()


class _HttpCurrentPatientProfileReader(CurrentPatientProfileBoundary):
    """HTTPテストで読取時点の患者プロフィールを返す境界Fake。"""

    def __init__(self) -> None:
        self.profile = MedicationHistoryPatientProfileDto(
            last_name="山田",
            first_name="花子",
            last_name_kana="ヤマダ",
            first_name_kana="ハナコ",
            birth_date="1980-01-02",
            gender="2",
            postal_code="1000001",
            address="東京都中央区一丁目",
            phone_number="03-0000-0000",
        )

    async def get_current_profile(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> MedicationHistoryPatientProfileDto | None:
        """指定患者に対応する現在プロフィールを返す。"""
        del corporate_id, patient_id
        return self.profile


@pytest.fixture
def current_patient_profile_reader() -> _HttpCurrentPatientProfileReader:
    """読取時点に切り替えられる患者プロフィール境界を返す。"""
    return _HttpCurrentPatientProfileReader()


def _start_history_body(
    fixture: history_helpers.MedicationHistoryFixture,
) -> dict[str, Any]:
    command = history_helpers.create_start_command(fixture)
    return StartMedicationHistoryRequest(
        store_id=command.store_id,
        dispensing_id=command.dispensing_id,
        method=command.method or "face_to_face",
        soap=command.soap,
        handbook_status=command.handbook_status or HandbookStatusInput(presented=True),
        residual_drug=command.residual_drug
        or ResidualDrugInput(has_residual_drugs=False),
        information_sheet_provided=command.information_sheet_provided,
        profile_updates=command.profile_updates,
    ).model_dump(mode="json")


def test_tc10_HTTP初回保存は_記載者を指導者にせず実記載を保存する(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    patient_id = str(history_fixture.patient_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    assert started.json().get("recorded_by") == str(history_fixture.counselor_id.value)
    assert started.json().get("counselor_id") is None
    assert started.json().get("counseled_at") is None

    # Act
    finalized = history_client.post(
        f"/corporates/{corporate_id}"
        f"/medication-histories/{started.json()['id']}/finalization",
        json={
            "counseled_at": history_fixture.clock.now().isoformat(),
            "review_result": "assessment_and_instruction_recorded",
        },
        headers=_HEADERS,
    )
    profile = history_client.get(
        f"/corporates/{corporate_id}/patients/{patient_id}/medical-profile",
        params={"as_of": "2026-08-30"},
        headers=_HEADERS,
    )

    # Assert
    assert finalized.status_code == HTTPStatus.OK, finalized.text
    assert finalized.json()["status"] == "finalized"
    assert finalized.json().get("reviewed_by") == str(
        history_fixture.counselor_id.value
    )
    assert (
        finalized.json().get("reviewed_at") == history_fixture.clock.now().isoformat()
    )
    assert profile.status_code == HTTPStatus.OK, profile.text
    assert profile.json()["patient_id"] == patient_id


def test_tc10b_HTTP部分SOAP初回保存と再保存は同じIDを更新する(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    authored_text = "食後の眠気が続くとの申告を記録する。"
    partial_body = {
        "store_id": str(history_fixture.store_id.value),
        "dispensing_id": str(history_fixture.dispensing.id.value),
        "soap": TypeAdapter(SoapInput).dump_python(
            SoapInput(
                subjective=(LabeledNoteInput(text=authored_text),),
            ),
            mode="json",
        ),
    }

    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=partial_body,
        headers=_HEADERS,
    )

    assert started.status_code == HTTPStatus.CREATED, started.text
    first = started.json()
    assert first.get("status") == "draft"
    assert first.get("soap", {}).get("subjective", [])[0]["text"] == authored_text
    assert first.get("soap", {}).get("objective") == []
    assert first.get("counseled_at") is None

    updated_text = "眠気の出現時刻と服用との関係を確認する。"
    update = history_client.put(
        f"/corporates/{corporate_id}/medication-histories/{first['id']}/draft",
        json={
            "soap": TypeAdapter(SoapInput).dump_python(
                SoapInput(
                    assessment=(LabeledNoteInput(text=updated_text),),
                ),
                mode="json",
            )
        },
        headers=_HEADERS,
    )

    assert update.status_code == HTTPStatus.OK, update.text
    assert update.json()["id"] == first["id"]
    assert update.json()["soap"]["assessment"][0]["text"] == updated_text
    assert len(history_fixture.record_repository.items) == 1


def test_HTTP初回保存は受付由来情報を引き継ぎSOAP本文を薬剤師の記載に保つ(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = history_fixture.corporate_id
    store_id = history_fixture.store_id
    reception_id = ReceptionId.generate()
    imported_at = history_fixture.clock.now() - timedelta(hours=2)
    reception = Reception(
        id=reception_id,
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=history_fixture.patient_id,
        latest_fingerprint=ReceptionFingerprint("a" * 64),
        field_fingerprints=(),
        prescription_id=history_fixture.dispensing.prescription_id,
        dispensing_id=history_fixture.dispensing.id,
        source_data=ReceptionSourceData(
            bundle_json="{}",
            imported_at=imported_at,
            billing_additions=(
                ReceptionBillingAddition(
                    code="140000110",
                    name="特定薬剤管理指導加算２",
                    points=100,
                    quantity=1,
                ),
            ),
        ),
    )
    history_fixture.reception_repository.items[
        (corporate_id, store_id, reception_id)
    ] = reception
    authored_text = "患者が話した眠気を薬剤師が記録する。"
    body = {
        "store_id": str(store_id.value),
        "dispensing_id": str(history_fixture.dispensing.id.value),
        "reception_id": str(reception_id.value),
        "soap": TypeAdapter(SoapInput).dump_python(
            SoapInput(subjective=(LabeledNoteInput(text=authored_text),)),
            mode="json",
        ),
    }

    response = history_client.post(
        f"/corporates/{corporate_id.value}/medication-histories",
        json=body,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    saved = response.json()
    assert saved["source_system"] == "NSIPS"
    assert saved["imported_at"] == imported_at.isoformat()
    assert saved["billing_additions"][0]["code"] == "140000110"
    assert saved["soap"]["subjective"][0]["text"] == authored_text
    assert saved["soap"]["objective"] == []
    assert saved["recorded_by"] == str(history_fixture.counselor_id.value)
    assert saved["counselor_id"] is None
    assert saved["counseled_at"] is None
    linked = history_fixture.reception_repository.items[
        (corporate_id, store_id, reception_id)
    ]
    assert linked.medication_history_id is not None
    assert str(linked.medication_history_id.value) == saved["id"]

    # 由来情報をHTTP入力から偽装できない。
    rejected = history_client.post(
        f"/corporates/{corporate_id.value}/medication-histories",
        json={
            **body,
            "source_system": "NSIPS",
            "imported_at": imported_at.isoformat(),
            "billing_additions": [],
        },
        headers=_HEADERS,
    )
    assert rejected.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, rejected.text
    assert len(history_fixture.record_repository.items) == 1


def test_tc12_HTTP白紙の初回保存は_薬歴を作らない(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    body = _start_history_body(history_fixture)
    body["soap"] = TypeAdapter(SoapInput).dump_python(SoapInput(), mode="json")
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=body,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, response.text
    assert history_fixture.record_repository.items == {}


def test_tc19_HTTPレビュー結果のない確定は_薬歴と頭書きを変更しない(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={},
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, response.text
    assert history_fixture.record_repository.items
    saved = next(iter(history_fixture.record_repository.items.values()))
    assert saved.is_finalized is False
    assert history_fixture.profile_repository.items == {}


def test_tc22_HTTPレビュー者は_Actorから決まり確定者とは別に返る(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    other_finalizer_id = StaffId.generate()
    history_fixture.staff_qualification.register(
        corporate_id=history_fixture.corporate_id,
        staff_id=other_finalizer_id,
        qualifications=create_pharmacist_qualifications(),
    )
    counseled_at = history_fixture.clock.now()

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/"
        f"{started.json()['id']}/finalization",
        json={
            "counseled_at": counseled_at.isoformat(),
            "finalized_by": str(other_finalizer_id.value),
            "review_result": "assessment_and_instruction_recorded",
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data.get("reviewed_by") == str(history_fixture.counselor_id.value)
    assert data.get("reviewed_at") == history_fixture.clock.now().isoformat()
    assert data.get("finalized_by") == str(other_finalizer_id.value)


def test_tc18_HTTP追加記載なしの確認は_本文に残して確定できる(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    body = _start_history_body(history_fixture)
    body["soap"] = TypeAdapter(SoapInput).dump_python(
        SoapInput(
            assessment=(
                LabeledNoteInput(
                    text="対象情報を確認し、追加記載事項はないと判断した。"
                ),
            ),
        ),
        mode="json",
    )
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=body,
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/"
        f"{started.json()['id']}/finalization",
        json={
            "counseled_at": history_fixture.clock.now().isoformat(),
            "review_result": "no_additional_recordable_items",
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json().get("review_result") == "no_additional_recordable_items"
    assert (
        response.json().get("soap", {}).get("assessment", [])[0]["text"]
        == "対象情報を確認し、追加記載事項はないと判断した。"
    )


def test_tc20_HTTP客観要約だけでは_確定できない(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    record = create_nsips_draft_record(
        corporate_id=history_fixture.corporate_id,
        store_id=history_fixture.store_id,
        patient_id=history_fixture.patient_id,
        dispensing_id=history_fixture.dispensing.id,
        prescription_id=history_fixture.dispensing.prescription_id,
        imported_at=history_fixture.clock.now() - timedelta(hours=2),
        ready_to_finalize=True,
    )
    record = replace(
        record,
        soap=SoapRecord(
            objective=(create_note("NSIPSから受信した処方・調剤の要約"),),
        ),
    )
    history_fixture.record_repository.items[record.id] = record

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/"
        f"{record.id.value}/finalization",
        json={
            "counseled_at": history_fixture.clock.now().isoformat(),
            "review_result": "assessment_and_instruction_recorded",
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, response.text
    assert response.json().get("code") != "REQUEST_VALIDATION_ERROR"
    stored = history_fixture.record_repository.items[record.id]
    assert stored.is_finalized is False
    assert history_fixture.profile_repository.items == {}


def test_tc09_起票本文のcounselor_idは_未知項目として拒否する(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    body = _start_history_body(history_fixture)
    body["counselor_id"] = "別スタッフのID"

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=body,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert history_fixture.record_repository.items == {}


def test_tc16_NSIPS下書き確定は_実指導情報を記録して取込時刻を残す(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    imported_at = history_fixture.clock.now()
    imported_record = create_nsips_draft_record(
        corporate_id=history_fixture.corporate_id,
        store_id=history_fixture.store_id,
        patient_id=history_fixture.patient_id,
        dispensing_id=history_fixture.dispensing.id,
        prescription_id=history_fixture.dispensing.prescription_id,
        imported_at=imported_at,
        ready_to_finalize=True,
    )
    history_fixture.record_repository.items[imported_record.id] = imported_record
    counseled_at = imported_at.replace(hour=1)

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/"
        f"{imported_record.id.value}/finalization",
        json={
            "counseled_at": counseled_at.isoformat(),
            "review_result": "assessment_and_instruction_recorded",
        },
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["counselor_id"] == str(history_fixture.counselor_id.value)
    assert response.json()["counseled_at"] == counseled_at.isoformat()
    assert response.json()["imported_at"] == imported_at.isoformat()


def test_tc17_実指導日時を省いて取込下書きを確定できない(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    corporate_id = str(history_fixture.corporate_id.value)
    imported_record = create_nsips_draft_record(
        corporate_id=history_fixture.corporate_id,
        store_id=history_fixture.store_id,
        patient_id=history_fixture.patient_id,
        dispensing_id=history_fixture.dispensing.id,
        prescription_id=history_fixture.dispensing.prescription_id,
        imported_at=history_fixture.clock.now(),
    )
    history_fixture.record_repository.items[imported_record.id] = imported_record

    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/"
        f"{imported_record.id.value}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert not history_fixture.record_repository.items[imported_record.id].is_finalized
    assert history_fixture.profile_repository.items == {}


def test_tc82_薬歴viewは_確定本文と読取時点の患者プロフィールを返す(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
    current_patient_profile_reader: _HttpCurrentPatientProfileReader,
) -> None:
    """保存済み薬歴本文を保ち、現行プロフィールを別項目で返す。"""
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]
    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text
    saved_record = history_client.get(
        f"/corporates/{corporate_id}/medication-histories/{record_id}",
        headers=_HEADERS,
    )
    assert saved_record.status_code == HTTPStatus.OK, saved_record.text

    current_patient_profile_reader.profile = MedicationHistoryPatientProfileDto(
        last_name="山田",
        first_name="花子",
        last_name_kana="ヤマダ",
        first_name_kana="ハナコ",
        birth_date="1980-01-02",
        gender="2",
        postal_code="1000001",
        address="東京都中央区二丁目",
        phone_number="03-0000-0000",
    )
    view = history_client.get(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/view",
        headers=_HEADERS,
    )

    assert view.status_code == HTTPStatus.OK, view.text
    assert view.json()["record"] == saved_record.json()
    assert view.json()["current_patient_profile"]["address"] == "東京都中央区二丁目"


def test_TC25_下書きの全項目更新と確定メタデータ付き確定(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    # Arrange: 起票
    corporate_id = str(history_fixture.corporate_id.value)
    started_res = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started_res.status_code == HTTPStatus.CREATED
    record_id = started_res.json()["id"]
    base = f"/corporates/{corporate_id}/medication-histories/{record_id}"

    # Act 1: 下書きの全項目更新 (PUT /draft)
    draft_update_body = UpdateMedicationHistoryDraftRequest(
        method="telephone",
        residual_drug=ResidualDrugInput(
            has_residual_drugs=True, quantity=10, reason="飲み忘れ"
        ),
        handbook_status=HandbookStatusInput(presented=True),
        information_sheet_provided=True,
        additional_notes=(
            CategorizedNoteInput(
                major_category_code="guidance",
                medium_category_code="adherence",
                text="服用タイミングを朝食後に変更指導。",
            ),
        ),
    ).model_dump(mode="json")
    update_res = history_client.put(
        f"{base}/draft",
        json=draft_update_body,
        headers=_HEADERS,
    )

    # Assert 1
    assert update_res.status_code == HTTPStatus.OK, update_res.text
    updated = update_res.json()
    assert updated["method"] == "telephone"
    assert updated["residual_drug"]["has_residual_drugs"] is True
    assert updated["residual_drug"]["quantity"] == 10
    assert updated["handbook_status"]["presented"] is True
    assert updated["information_sheet_provided"] is True
    assert len(updated["additional_notes"]) == 1
    assert updated["status"] == "draft"

    # Act 2: 確定 (POST /finalization) - 確定者資格の検証と確定メタデータの記録
    counselor_str = str(history_fixture.counselor_id.value)
    finalize_res = history_client.post(
        f"{base}/finalization",
        json=FinalizeMedicationHistoryRequest(
            finalized_by=counselor_str,
            review_result="assessment_and_instruction_recorded",
        ).model_dump(mode="json"),
        headers=_HEADERS,
    )

    # Assert 2
    assert finalize_res.status_code == HTTPStatus.OK, finalize_res.text
    finalized = finalize_res.json()
    assert finalized["status"] == "finalized"
    assert finalized["finalized_by"] == counselor_str
    assert finalized["finalized_at"] is not None
    assert finalized["delay_reason"] is None


def test_確定済みの薬歴は_訂正として積まれる(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    ).json()
    base = f"/corporates/{corporate_id}/medication-histories/{started['id']}"
    history_client.post(
        f"{base}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    amended_soap = history_helpers.create_soap_input(
        subjective="訂正後の聞き取り内容。"
    )

    # Act
    amended = history_client.post(
        f"{base}/amendments",
        json={
            "amended_by": str(history_fixture.counselor_id.value),
            "reason": "記載誤りの訂正。",
            "amended_soap": TypeAdapter(SoapInput).dump_python(
                amended_soap, mode="json"
            ),
        },
        headers=_HEADERS,
    )

    # Assert
    assert amended.status_code == HTTPStatus.CREATED, amended.text
    assert len(amended.json()["amendments"]) == 1


def test_患者ごとの薬歴一覧が引ける(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    patient_id = str(history_fixture.patient_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )

    # Act
    listed = history_client.get(
        f"/corporates/{corporate_id}/patients/{patient_id}/medication-histories",
        headers=_HEADERS,
    )

    # Assert
    assert listed.status_code == HTTPStatus.OK
    assert [item["id"] for item in listed.json()] == [started.json()["id"]]


def test_確定済の薬歴は_調剤録の代替可否を返す(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """記載事項の充足は、号ごとの判定として外から読める必要がある。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]
    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text

    # Act
    response = history_client.get(
        f"/corporates/{corporate_id}"
        f"/medication-histories/{record_id}/statutory-record-sufficiency",
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["record_id"] == record_id
    assert body["substitutes_dispensing_record"] is True
    assert body["blockers"] == []
    assert len(body["assessments"]) == len(StatutoryDispensingRecordItem)


def test_確定済みの薬歴にフォローアップを追加できる(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-01: 確定済み薬歴にフォローアップを追加して 201 CREATED が返る。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]
    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text

    body = AddFollowUpRequest(
        counselor_id=str(history_fixture.counselor_id.value),
        followed_up_at=datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        method="telephone",
        soap=history_helpers.create_soap_input(
            subjective="服用後の体調確認。問題なし。"
        ),
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/follow-ups",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.CREATED, response.text
    result = response.json()
    assert len(result["follow_ups"]) == 1
    assert result["follow_ups"][0]["counselor_id"] == str(
        history_fixture.counselor_id.value
    )
    assert result["follow_ups"][0]["method"] == "telephone"


def test_未確定の下書き薬歴にフォローアップを追加すると422が返る(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-02: 未確定（下書き）の薬歴にフォローアップを追加すると 422 UNPROCESSABLE_CONTENT。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    body = AddFollowUpRequest(
        counselor_id=str(history_fixture.counselor_id.value),
        followed_up_at=datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        method="telephone",
        soap=history_helpers.create_soap_input(
            subjective="服用後の体調確認。問題なし。"
        ),
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/follow-ups",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"]


def test_確定済みの薬歴にトレーシングレポートを追加できる(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-01: 確定済みの薬歴にトレーシングレポートを追加して 201 CREATED。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text

    body = RecordTracingReportRequest(
        reporter_id=str(history_fixture.counselor_id.value),
        provided_at=datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        medical_institution_name="総合病院",
        physician_name="山田医師",
        category="residual_drug",
        fee_category="fee_1",
        delivery_method="fax",
        content="残薬7日分あり",
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.CREATED, response.text
    result = response.json()
    assert len(result["tracing_reports"]) == 1
    report = result["tracing_reports"][0]
    assert report["reporter_id"] == str(history_fixture.counselor_id.value)
    assert report["medical_institution_name"] == "総合病院"
    assert report["physician_name"] == "山田医師"
    assert report["category"] == "residual_drug"
    assert report["fee_category"] == "fee_1"
    assert report["delivery_method"] == "fax"
    assert report["content"] == "残薬7日分あり"
    assert report["response"] is None


def test_トレーシングレポートに医師返答を記録できる(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-02: トレーシングレポートに対する医師返答を記録して 200 OK。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text

    report_body = RecordTracingReportRequest(
        reporter_id=str(history_fixture.counselor_id.value),
        provided_at=datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        medical_institution_name="総合病院",
        physician_name="山田医師",
        category="residual_drug",
        fee_category="fee_1",
        delivery_method="fax",
        content="残薬7日分あり",
    ).model_dump(mode="json")

    report_response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports",
        json=report_body,
        headers=_HEADERS,
    )
    assert report_response.status_code == HTTPStatus.CREATED, report_response.text
    report_id = report_response.json()["tracing_reports"][0]["id"]

    resp_body = RecordTracingReportResponseRequest(
        responded_at=datetime(2026, 9, 4, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        content="次回処方時に7日分減数します",
        action_type="agreed_reflect_next",
        received_by=str(history_fixture.counselor_id.value),
        acknowledged_physician_name="山田医師",
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports/{report_id}/response",
        json=resp_body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.OK, response.text
    result = response.json()
    resp_data = result["tracing_reports"][0]["response"]
    assert resp_data is not None
    assert resp_data["content"] == "次回処方時に7日分減数します"
    assert resp_data["action_type"] == "agreed_reflect_next"
    assert resp_data["received_by"] == str(history_fixture.counselor_id.value)
    assert resp_data["acknowledged_physician_name"] == "山田医師"


def test_未確定の下書き薬歴にトレーシングレポートを追加すると422が返る(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-03: 未確定（下書き）の薬歴にトレーシングレポートを追加すると 422 UNPROCESSABLE_CONTENT。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    body = RecordTracingReportRequest(
        reporter_id=str(history_fixture.counselor_id.value),
        provided_at=datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        medical_institution_name="総合病院",
        physician_name="山田医師",
        category="residual_drug_adjustment",
        fee_category="fee_1",
        delivery_method="fax",
        content="残薬7日分あり",
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports",
        json=body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, response.text
    assert response.json()["code"]


def test_存在しないレポートIDに返答を記録すると404が返る(
    history_client: TestClient,
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> None:
    """TC-HTTP-04: 存在しないレポートIDに返答を記録すると 404 NOT_FOUND。"""
    # Arrange
    corporate_id = str(history_fixture.corporate_id.value)
    started = history_client.post(
        f"/corporates/{corporate_id}/medication-histories",
        json=_start_history_body(history_fixture),
        headers=_HEADERS,
    )
    assert started.status_code == HTTPStatus.CREATED, started.text
    record_id = started.json()["id"]

    finalized = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/finalization",
        json={"review_result": "assessment_and_instruction_recorded"},
        headers=_HEADERS,
    )
    assert finalized.status_code == HTTPStatus.OK, finalized.text

    resp_body = RecordTracingReportResponseRequest(
        responded_at=datetime(2026, 9, 4, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        content="了解しました",
        action_type="acknowledged",
        received_by=str(history_fixture.counselor_id.value),
    ).model_dump(mode="json")

    # Act
    response = history_client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports/0191eb70-0000-7000-8000-000000000099/response",
        json=resp_body,
        headers=_HEADERS,
    )

    # Assert
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
