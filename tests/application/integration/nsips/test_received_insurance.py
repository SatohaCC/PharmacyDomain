"""保険・公費情報は資格台帳へ変換せず受付の受信事実として保存する。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import date

import pytest

from app.application.composition.prescription_references import (
    PrescriptionPatientReferenceAdapter,
)
from app.application.coverage.register_patient_coverage import (
    RegisterPatientCoverageCommand,
    RegisterPatientCoverageUseCase,
)
from app.application.integration.nsips.ingest_nsips import IngestNsipsCommand
from app.application.integration.nsips.models import NsipsBundle, NsipsInsuranceInfo
from app.application.integration.nsips.parser import NsipsParser
from app.domain.coverage.services import PatientCoverageConflictService
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import ReceptionId
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.integration.nsips.helpers import create_fixture

_INSURANCE = NsipsInsuranceInfo(
    insurer_number="138001",
    insured_symbol="記号A",
    insured_number="番号123",
    branch_number="01",
    insured_type="self",
    benefit_ratio=70,
)


def _bundle() -> NsipsBundle:
    """合成処方を構造化入力にし、受信保険情報を付ける。"""
    parsed = NsipsParser().parse(
        "1,20260920,DOC-INSURANCE-1,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-INSURANCE,ヤマダタロウ,山田太郎,1,19800101\n"
        "4,20260920,REC-001,調剤花子\n"
        "5,1,内服,1日1回,7,1,610406001,アムロジピン,1,錠,0\n"
    )
    return replace(
        parsed,
        insurance=_INSURANCE,
    )


@pytest.mark.parametrize(
    "insurance",
    (
        _INSURANCE,
        replace(_INSURANCE, insurer_number="138002"),
        replace(_INSURANCE, branch_number="02"),
        replace(_INSURANCE, branch_number=None),
        replace(_INSURANCE, benefit_ratio=80),
        replace(_INSURANCE, benefit_ratio=None, insured_type=None),
        NsipsInsuranceInfo(
            insurer_number="",
            insured_symbol="",
            insured_number="",
            public_payer_number_2="54130012",
            public_recipient_number_2="1234567",
        ),
        replace(_INSURANCE, public_payer_number_1="54130012"),
    ),
    ids=(
        "同一保険",
        "保険者変更",
        "枝番変更",
        "枝番欠損",
        "給付割合変更",
        "割合区分不明",
        "第二公費のみ",
        "公費片側欠損",
    ),
)
@pytest.mark.asyncio
async def test_受付取込_保険情報を別受付で受信_原本を保存し資格を自動選択しない(
    insurance: NsipsInsuranceInfo,
) -> None:
    # Arrange
    fixture = await create_fixture()
    first_command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(ReceptionId.generate().value),
        structured_bundle=_bundle(),
    )
    first = await fixture.use_case.execute(first_command)
    original = fixture.reception_repo.items.copy()
    second_id = ReceptionId.generate()
    second_bundle = replace(
        _bundle(),
        prescription=replace(_bundle().prescription, document_number="DOC-INSURANCE-2"),
        insurance=insurance,
    )
    second_command = replace(
        first_command,
        reception_id=str(second_id.value),
        structured_bundle=second_bundle,
    )

    # Act
    second = await fixture.use_case.execute(second_command)
    resent = await fixture.use_case.execute(second_command)

    # Assert
    assert second.patient_id == first.patient_id
    assert second.prescription_id is not None
    assert second.dispensing_id is not None
    assert second.coverage_selection_record_id is None
    assert resent.is_duplicate is True
    assert resent.prescription_id == second.prescription_id
    assert len(fixture.prescription_repo.items) == 2
    assert len(fixture.dispensing_repo.items) == 2
    assert fixture.patient_coverage_repo.items == {}
    assert fixture.coverage_selection_repo.items == {}
    for key, reception in original.items():
        assert fixture.reception_repo.items[key] == reception
    stored = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=second_id,
    )
    assert stored is not None and stored.source_data is not None
    assert json.loads(stored.source_data.bundle_json)["insurance"] == asdict(insurance)
    assert stored.source_data_history == ()


@pytest.mark.parametrize("expired", (False, True), ids=("終了日なし", "適用日前に失効"))
@pytest.mark.asyncio
async def test_受付取込_既存資格がある_変更せず受信情報を保存する(
    expired: bool,
) -> None:
    # Arrange
    fixture = await create_fixture()
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(ReceptionId.generate().value),
        structured_bundle=_bundle(),
    )
    first = await fixture.use_case.execute(command)
    register = RegisterPatientCoverageUseCase(
        repository=fixture.patient_coverage_repo,
        patient_reference=PrescriptionPatientReferenceAdapter(fixture.patient_repo),
        conflict_service=PatientCoverageConflictService(),
        corporate_access=create_vendor_corporate_access_for(fixture.corporate_repo),
    )
    await register.execute(
        RegisterPatientCoverageCommand(
            corporate_id=command.corporate_id,
            patient_id=first.patient_id,
            coverage_type="insurance",
            valid_from=date(2026, 9, 1),
            valid_to=date(2026, 9, 19) if expired else None,
            activated_on=date(2026, 9, 1),
            priority=1,
            insurer_number="138001",
            insured_symbol="記号A",
            insured_number="番号123",
            branch_number="01",
            insured_type="self",
            benefit_ratio=70,
        )
    )
    before = fixture.patient_coverage_repo.items.copy()
    incoming = _bundle()
    assert incoming.insurance is not None
    incoming = replace(
        incoming,
        insurance=replace(
            incoming.insurance, insurer_number="138001" if expired else "138002"
        ),
        prescription=replace(incoming.prescription, document_number="DOC-INSURANCE-2"),
    )

    # Act
    result = await fixture.use_case.execute(
        replace(
            command,
            reception_id=str(ReceptionId.generate().value),
            structured_bundle=incoming,
        )
    )

    # Assert
    assert result.prescription_id is not None and result.dispensing_id is not None
    assert result.coverage_selection_record_id is None
    assert fixture.patient_coverage_repo.items == before
    assert fixture.coverage_selection_repo.items == {}
    assert await fixture.patient_coverage_repo.list_by_patient(
        corporate_id=fixture.corporate_id, patient_id=PatientId.parse(first.patient_id)
    )


@pytest.mark.parametrize("follow_up", (False, True), ids=("処方受付", "薬品なし受付"))
@pytest.mark.asyncio
async def test_受付取込_同一受付の保険訂正_受信履歴を保持し再送で重複しない(
    follow_up: bool,
) -> None:
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _bundle()
    if follow_up:
        bundle = replace(bundle, prescription=replace(bundle.prescription, rps=()))
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(reception_id.value),
        structured_bundle=bundle,
    )
    first = await fixture.use_case.execute(command)
    changed_insurance = replace(_INSURANCE, insurer_number="138002", benefit_ratio=None)
    changed = replace(
        command, structured_bundle=replace(bundle, insurance=changed_insurance)
    )

    # Act
    corrected = await fixture.use_case.execute(changed)
    resent = await fixture.use_case.execute(changed)

    # Assert
    assert corrected.prescription_id == first.prescription_id
    assert corrected.dispensing_id == first.dispensing_id
    assert corrected.coverage_review_required is True
    assert resent.is_duplicate is True
    assert resent.coverage_review_required is True
    assert resent.coverage_review_reason == "benefit_ratio_missing"
    stored = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert stored is not None and stored.source_data is not None
    assert json.loads(stored.source_data.bundle_json)["insurance"] == asdict(
        changed_insurance
    )
    assert len(stored.source_data_history) == 1
    assert json.loads(stored.source_data_history[0].bundle_json)["insurance"] == asdict(
        _INSURANCE
    )
    assert len(stored.correction_history) == 1
    assert len(fixture.reception_repo.items) == 1
    assert len(fixture.prescription_repo.items) == (0 if follow_up else 1)
    assert len(fixture.dispensing_repo.items) == (0 if follow_up else 1)
    assert fixture.patient_coverage_repo.items == {}
    assert fixture.coverage_selection_repo.items == {}
