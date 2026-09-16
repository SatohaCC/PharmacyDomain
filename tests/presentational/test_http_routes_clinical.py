"""処方箋・調剤・薬歴のHTTPルートの振る舞い。

この3つは参照Boundaryを多数必要とするため、``conftest.py`` の土台には載せず、
Application層テストの Fixture をそのまま束へ入れ替える。入力は入れ子が深いので、
本文もルータのリクエストモデルから ``model_dump(mode="json")`` で作る。手書きの
JSONを置くと、Application層の項目が増えたときにテストだけ古いまま緑になる。
"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.application.medication_history import SoapInput
from app.infrastructure.di import (
    DispensingUseCases,
    MedicationHistoryUseCases,
    PrescriptionUseCases,
)
from app.presentational import create_app
from app.presentational.dependencies import (
    get_dispensing_use_cases,
    get_medication_history_use_cases,
    get_prescription_use_cases,
)
from app.presentational.routers.dispensing import StartDispensingRequest
from app.presentational.routers.medication_history import (
    StartMedicationHistoryRequest,
)
from app.presentational.routers.prescription import RegisterPrescriptionRequest
from tests.application.dispensing import helpers as dispensing_helpers
from tests.application.medication_history import helpers as history_helpers
from tests.application.prescription import helpers as prescription_helpers
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


# --- 薬歴 -------------------------------------------------------------------


@pytest.fixture
def history_fixture() -> history_helpers.MedicationHistoryFixture:
    return history_helpers.create_fixture()


@pytest.fixture
def history_client(
    history_fixture: history_helpers.MedicationHistoryFixture,
) -> Iterator[TestClient]:
    bundle = MedicationHistoryUseCases(
        start=history_fixture.start,
        update_draft=history_fixture.update_draft,
        finalize=history_fixture.finalize,
        amend=history_fixture.amend,
        get=history_fixture.get,
        list_by_patient=history_fixture.list_by_patient,
        get_medical_profile=history_fixture.get_profile,
        rebuild_medical_profile=history_fixture.rebuild_profile,
    )
    yield from _client({get_medication_history_use_cases: lambda: bundle})


def _start_history_body(
    fixture: history_helpers.MedicationHistoryFixture,
) -> dict[str, Any]:
    command = history_helpers.create_start_command(fixture)
    return StartMedicationHistoryRequest(
        store_id=command.store_id,
        dispensing_id=command.dispensing_id,
        counselor_id=command.counselor_id,
        method=command.method,
        soap=command.soap,
        handbook_status=command.handbook_status,
        residual_drug=command.residual_drug,
        information_sheet_provided=command.information_sheet_provided,
        profile_updates=command.profile_updates,
    ).model_dump(mode="json")


def test_薬歴を起票して確定すると_頭書きへ投影される(
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

    # Act
    finalized = history_client.post(
        f"/corporates/{corporate_id}"
        f"/medication-histories/{started.json()['id']}/finalization",
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
    assert profile.status_code == HTTPStatus.OK, profile.text
    assert profile.json()["patient_id"] == patient_id


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
    history_client.post(f"{base}/finalization", headers=_HEADERS)
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
