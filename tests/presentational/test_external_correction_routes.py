"""外部訂正レビューのHTTP公開契約を確認する。"""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Any, Literal, cast

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.application.medication_history.list_pending_external_corrections import (
    ListPendingExternalCorrectionsUseCase,
)
from app.application.medication_history.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionUseCase,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    FinalizedTimestamp,
)
from app.domain.medication_history.value_objects import (
    ExternalCorrectionKind,
    ExternalPrescriptionCorrection,
)
from app.infrastructure.di.bundles.clinical import MedicationHistoryUseCases
from app.presentational.app_factory import create_app
from app.presentational.dependencies import get_medication_history_use_cases
from app.presentational.routers.medication_history import router as history_router
from app.presentational.routers.nsips import (
    NsipsBundleRequest,
    NsipsPatientRequest,
    NsipsPrescriptionRequest,
    _build_bundle_from_request,
)
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_record,
    create_soap,
    finalize_record_with_review,
)
from tests.factories.prescription_factory import create_prescription
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)

_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture
def history_fixture() -> MedicationHistoryFixture:
    return create_fixture()


@pytest.fixture
def prescription_repo() -> InMemoryPrescriptionRepository:
    return InMemoryPrescriptionRepository()


@pytest.fixture
def client(
    history_fixture: MedicationHistoryFixture,
    prescription_repo: InMemoryPrescriptionRepository,
) -> Iterator[TestClient]:
    bundle = MedicationHistoryUseCases(
        start=history_fixture.start,
        update_draft=history_fixture.update_draft,
        finalize=history_fixture.finalize,
        amend=history_fixture.amend,
        correct_fact=cast(Any, None),
        get=history_fixture.get,
        get_follow_up_source=cast(Any, None),
        list_by_patient=history_fixture.list_by_patient,
        get_medical_profile=history_fixture.get_profile,
        rebuild_medical_profile=history_fixture.rebuild_profile,
        verify_statutory_record=history_fixture.verify_statutory_record,
        get_category_catalog=history_fixture.get_category_catalog,
        update_category_catalog=history_fixture.update_category_catalog,
        record_tracing_report=history_fixture.record_tracing_report,
        record_tracing_report_response=history_fixture.record_tracing_report_response,
        get_view=cast(Any, None),
        list_external_corrections=ListPendingExternalCorrectionsUseCase(
            history_fixture.record_repository,
            history_fixture.corporate_access,
        ),
        review_external_correction=ReviewExternalPrescriptionCorrectionUseCase(
            history_fixture.record_repository,
            history_fixture.corporate_access,
            history_fixture.staff_qualification,
            prescription_repo,
            history_fixture.clock,
        ),
    )
    app = create_app(actor_provider=StubActorContextProvider(history_fixture.actor))
    app.dependency_overrides[get_medication_history_use_cases] = lambda: bundle
    yield TestClient(app)
    app.dependency_overrides.clear()


async def _store_pending_record(
    fixture: MedicationHistoryFixture,
    correction_kind: ExternalCorrectionKind = ExternalCorrectionKind.UPDATE,
) -> MedicationHistoryRecord:
    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        dispensing_id=fixture.dispensing.id,
        prescription_id=fixture.dispensing.prescription_id,
        counseled_at=COUNSELED_AT,
        soap=create_soap(subjective="原本の指導記録。"),
    )
    record = finalize_record_with_review(
        draft,
        finalized_at=FinalizedTimestamp(COUNSELED_AT),
        finalized_by=fixture.counselor_id,
    ).record_external_correction(
        ExternalPrescriptionCorrection(
            correction_id="corr-http-001",
            corrected_at=ExternalCorrectionTimestamp(
                datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
            ),
            source_document_number="RX-HTTP-001",
            reason="NSIPS外部処方訂正",
            kind=correction_kind,
        )
    )
    await fixture.record_repository.save(record)
    return record


def test_TC26_外部訂正の一覧と判断APIを公開する() -> None:
    paths = {
        route.path for route in history_router.routes if isinstance(route, APIRoute)
    }

    assert "/corporates/{corporate_id}/medication-history-external-corrections" in paths
    assert (
        "/corporates/{corporate_id}/medication-histories/{record_id}/"
        "external-corrections/{correction_id}/reviews"
    ) in paths


@pytest.mark.asyncio
async def test_TC27_HTTP_AMENDレビューで追記と判断履歴を記録する(
    client: TestClient,
    history_fixture: MedicationHistoryFixture,
) -> None:
    record = await _store_pending_record(history_fixture)
    corporate_id = str(history_fixture.corporate_id.value)
    record_id = str(record.id.value)
    correction_id = "corr-http-001"

    body = {
        "decision": "amend",
        "reason": "変更内容を患者へ説明し、指導内容を追記した。",
        "amended_soap": {
            "subjective": [
                {
                    "category": "patient_condition_change",
                    "text": "変更内容の説明を追記。",
                }
            ]
        },
    }

    response = client.post(
        f"/corporates/{corporate_id}/medication-histories/{record_id}/"
        f"external-corrections/{correction_id}/reviews",
        json=body,
        headers=_HEADERS,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["external_corrections"][0]["status"] == "resolved"
    review_event = data["external_corrections"][0]["review_events"][-1]
    assert review_event["decision"] == "amend"
    assert review_event["reason"] == "変更内容を患者へ説明し、指導内容を追記した。"
    assert review_event["reviewed_by"] == str(history_fixture.counselor_id.value)
    assert len(data["amendments"]) == 1
    assert (
        data["amendments"][0]["reason"]
        == "変更内容を患者へ説明し、指導内容を追記した。"
    )
    assert data["soap"]["subjective"][0]["text"] == "原本の指導記録。"


@pytest.mark.asyncio
async def test_TC28_HTTP_判断種別ごとの入力検証(
    client: TestClient,
    history_fixture: MedicationHistoryFixture,
    prescription_repo: InMemoryPrescriptionRepository,
) -> None:
    record = await _store_pending_record(
        history_fixture, correction_kind=ExternalCorrectionKind.DELETE
    )
    corporate_id = str(history_fixture.corporate_id.value)
    record_id = str(record.id.value)
    correction_id = "corr-http-001"
    url = (
        f"/corporates/{corporate_id}/medication-histories/{record_id}/"
        f"external-corrections/{correction_id}/reviews"
    )

    # 1. 理由なし不採用（空白理由は422）
    res_blank_reason = client.post(
        url,
        json={"decision": "no_action", "reason": "   "},
        headers=_HEADERS,
    )
    assert res_blank_reason.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 2. 調査中（成功）
    res_investigating = client.post(
        url,
        json={"decision": "investigating", "reason": "処方元へ疑義確認中。"},
        headers=_HEADERS,
    )
    assert res_investigating.status_code == HTTPStatus.OK
    assert res_investigating.json()["external_corrections"][0]["status"] == (
        "investigating"
    )

    # 3. 照合判断（照合先処方IDなしは422）
    res_match_missing = client.post(
        url,
        json={"decision": "match_reregistered_prescription", "reason": "照合"},
        headers=_HEADERS,
    )
    assert res_match_missing.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 4. 照合判断（有効な処方IDで成功）
    matched_rx = create_prescription(
        corporate_id=history_fixture.corporate_id,
        store_id=history_fixture.store_id,
        patient_id=history_fixture.patient_id,
    )
    await prescription_repo.save(matched_rx)
    res_match_valid = client.post(
        url,
        json={
            "decision": "match_reregistered_prescription",
            "reason": "再登録処方との一致を確認した。",
            "matched_prescription_id": str(matched_rx.id.value),
        },
        headers=_HEADERS,
    )
    assert res_match_valid.status_code == HTTPStatus.OK
    data = res_match_valid.json()
    assert data["external_corrections"][0]["status"] == "resolved"
    assert data["external_corrections"][0]["review_events"][-1][
        "matched_prescription_id"
    ] == str(matched_rx.id.value)


@pytest.mark.asyncio
async def test_TC29_HTTP_監査値の偽装防止(
    client: TestClient,
    history_fixture: MedicationHistoryFixture,
) -> None:
    record = await _store_pending_record(history_fixture)
    corporate_id = str(history_fixture.corporate_id.value)
    record_id = str(record.id.value)
    correction_id = "corr-http-001"
    url = (
        f"/corporates/{corporate_id}/medication-histories/{record_id}/"
        f"external-corrections/{correction_id}/reviews"
    )

    # クライアントから担当者IDや処理日時を偽装して送信する
    body_with_extra = {
        "decision": "no_action",
        "reason": "監査項目の偽装防止確認。",
        "reviewed_by": "0191eb70-0000-7000-8000-000000000999",
        "reviewed_at": "2020-01-01T00:00:00Z",
    }

    response = client.post(url, json=body_with_extra, headers=_HEADERS)

    # RequestModelのextra="forbid"により422 UNPROCESSABLE_ENTITYで拒否される
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text

    # レコードの状態が変更されていないことを確認
    saved = await history_fixture.record_repository.get(
        corporate_id=history_fixture.corporate_id, record_id=record.id
    )
    assert saved is not None
    assert saved.external_corrections[0].review_events == ()


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("update", ExternalCorrectionKind.UPDATE),
        ("delete", ExternalCorrectionKind.DELETE),
    ],
)
def test_TC30_正規化済み更新削除区分をBundleへ保持する(
    kind: Literal["update", "delete"],
    expected: ExternalCorrectionKind,
) -> None:
    request = NsipsBundleRequest(
        patient=NsipsPatientRequest(
            external_patient_id="patient-001",
            kanji_name="山田 花子",
            kana_name="ヤマダ ハナコ",
            birth_date=date(1980, 1, 2),
        ),
        prescription=NsipsPrescriptionRequest(
            document_number="RX-20260824-001",
            issued_date=date(2026, 8, 24),
            institution_code="1234567",
            institution_name="テスト医療機関",
            doctor_name="担当医",
            rps=(),
        ),
        correction_kind=kind,
    )

    bundle = _build_bundle_from_request(request)

    assert bundle.correction_kind is expected
