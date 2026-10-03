"""NSIPS Uファイル（処方訂正）取込時の真正性管理テスト。"""

from __future__ import annotations

import inspect
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.application.composition.reception_medication_history import (
    ReceptionMedicationHistoryAssociationAdapter,
)
from app.application.integration.nsips.exceptions import (
    NsipsPatientIdentityConflictError,
)
from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
    IngestNsipsResultDto,
)
from app.application.integration.nsips.models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)
from app.application.reception.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryCommand,
    AssociateReceptionMedicationHistoryUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId, DispensingProcessStatus
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    BillingAdditionCode,
    BillingAdditionName,
    CounselingMethod,
    CounselingTimestamp,
    ExternalCorrectionTimestamp,
    FinalizedTimestamp,
    MedicationHistoryImportTimestamp,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    ExternalCorrectionDecision,
    ExternalCorrectionKind,
    ExternalCorrectionStatus,
    HandbookStatus,
    ResidualDrugRecord,
)
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.heading import PatientHeadingContent, PatientHeadingText
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientAddress,
    PatientId,
)
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionId,
    PrescriptionStatus,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.reception import ReceptionSourceData
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.medicine import MedicineCode, MedicineCodeType, MedicineName
from app.domain.shared.person_name import PersonNames
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.integration.nsips.helpers import (
    NsipsFixture,
    create_fixture,
    execute_structured_test_command,
)
from tests.factories.dispensing_factory import complete_dispensing
from tests.factories.medication_history_factory import (
    create_independent_follow_up_record,
    create_record,
    create_soap,
    finalize_record_with_review,
)
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_store


async def _save_history_after_pharmacist_writing(
    fixture: NsipsFixture,
    *,
    reception_id: ReceptionId,
    ingest_result: IngestNsipsResultDto,
) -> MedicationHistoryRecord:
    """U-file回帰用に、薬剤師の初回保存後の薬歴と受付リンクを準備する。"""
    assert ingest_result.medication_history_id is None
    assert fixture.medication_history_repo.items == {}
    dispensing_id_value = ingest_result.dispensing_id
    patient_id_value = ingest_result.patient_id
    assert dispensing_id_value is not None
    dispensing_id = DispensingId.parse(dispensing_id_value)
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert dispensing is not None
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.source_data is not None
    record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=PatientId.parse(patient_id_value),
        dispensing_id=dispensing_id,
        prescription_id=dispensing.prescription_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now(),
        soap=create_soap(subjective="薬剤師が初回保存した記録。"),
        billing_additions=tuple(
            BillingAddition(
                code=BillingAdditionCode(item.code),
                name=BillingAdditionName(item.name),
                points=item.points,
                quantity=item.quantity,
            )
            for item in reception.source_data.billing_additions
        ),
    )
    record = replace(
        record,
        source_system=MedicationHistorySourceSystem("NSIPS"),
        imported_at=MedicationHistoryImportTimestamp(reception.source_data.imported_at),
    )
    await fixture.medication_history_repo.save(record)
    await fixture.reception_repo.save(
        replace(reception, medication_history_id=record.id)
    )
    return record


@pytest.mark.asyncio
async def test_tc08_Uファイル保留を薬剤師が指定した薬歴だけに関連付ける() -> None:
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-PENDING-UFILE"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    assert initial.patient_id
    assert initial.dispensing_id is not None
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    fixture.medication_history_repo.items.clear()
    source_data = ReceptionSourceData(
        bundle_json='{"prescription":{"rps":[]},"follow_up":{"kind":"U"}}',
        imported_at=fixture.clock.now(),
        is_follow_up=True,
    )
    pending_reception = replace(
        reception,
        medication_history_id=None,
        source_data=source_data,
    )
    await fixture.reception_repo.save(pending_reception)
    dispensing_id = DispensingId.parse(initial.dispensing_id)
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert dispensing is not None
    selected_record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=PatientId.parse(initial.patient_id),
        dispensing_id=dispensing_id,
        prescription_id=dispensing.prescription_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now(),
        soap=create_soap(subjective="選択された薬歴の既存SOAP。"),
    )
    other_record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=PatientId.parse(initial.patient_id),
        dispensing_id=dispensing_id,
        prescription_id=dispensing.prescription_id,
        counselor_id=fixture.pharmacist_id,
        counseled_at=fixture.clock.now(),
        soap=create_soap(subjective="別の薬歴の既存SOAP。"),
    )
    await fixture.medication_history_repo.save(selected_record)
    await fixture.medication_history_repo.save(other_record)
    selected_soap = selected_record.soap
    other_soap = other_record.soap
    use_case = AssociateReceptionMedicationHistoryUseCase(
        reception_repository=fixture.reception_repo,
        medication_history_reference=ReceptionMedicationHistoryAssociationAdapter(
            fixture.medication_history_repo
        ),
        corporate_access=create_vendor_corporate_access_for(fixture.corporate_repo),
        unit_of_work=fixture.unit_of_work,
    )

    associated = await use_case.execute(
        AssociateReceptionMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(reception_id.value),
            medication_history_id=str(selected_record.id.value),
        )
    )

    assert associated.medication_history_id == str(selected_record.id.value)
    associated_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert associated_reception is not None
    assert associated_reception.medication_history_id == selected_record.id
    assert associated_reception.source_data == source_data
    assert (
        fixture.medication_history_repo.items[selected_record.id].soap == selected_soap
    )
    assert fixture.medication_history_repo.items[other_record.id].soap == other_soap


@pytest.mark.asyncio
async def test_ingest_u_file_with_finalized_history_records_correction() -> None:
    """確定済み薬歴が存在する処方箋のUファイルを訂正証跡として保管する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()

    # 1. 初回受付（7日分処方）
    raw_initial = (
        "1,20260922,DOC-U01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9001,ヤマダタロウ,山田太郎,1,19800101\n"
        "4,20260922,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=raw_initial,
        ),
    )
    saved_history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=res_initial
    )
    history_id = saved_history.id

    # 2. 薬剤師が服薬指導を完了し薬歴を「確定（FINALIZED）」する
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    finalized_history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(finalized_history)

    # 3. レセコン側で疑義照会等により日数変更され、同一処方箋番号でUファイル（5日分処方）が再送される
    raw_u_file = (
        "1,20260922,DOC-U01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9001,ヤマダタロウ,山田太郎,1,19800101\n"
        "4,20260922,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,5,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_u_file = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=raw_u_file,
        ),
    )

    # 4. 検証: 取込結果DTOで要確認が報告される
    assert res_u_file.has_pending_correction_review is True
    assert res_u_file.is_duplicate is False

    # 5. 検証: 確定薬歴の原本が1文字も破壊されていないこと（不可逆凍結の真正性保証）
    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert reloaded_history is not None
    assert reloaded_history.soap == finalized_history.soap
    assert reloaded_history.counseled_at == finalized_history.counseled_at
    assert reloaded_history.finalized_at == finalized_history.finalized_at
    assert reloaded_history.finalized_by == finalized_history.finalized_by
    assert reloaded_history.is_finalized is True

    # 6. 検証: 外部処方訂正の監査証跡が記録されていること
    assert len(reloaded_history.external_corrections) == 1
    assert reloaded_history.has_pending_correction_review is True


@pytest.mark.asyncio
async def test_ingest_u_file_with_draft_history() -> None:
    """下書き薬歴が存在する処方箋のUファイル取込動作を確認する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()

    # 1. 初回受付
    raw_initial = (
        "1,20260922,DOC-U02,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9002,サトウハナコ,佐藤花子,2,19850505\n"
        "4,20260922,REC-002,調剤花子\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=raw_initial,
        ),
    )
    saved_history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=res_initial
    )
    history_id = saved_history.id

    # 2. 薬歴は確定せず下書き（DRAFT）のままUファイル（7日分に変更）を受信
    raw_u_file = (
        "1,20260922,DOC-U02,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9002,サトウハナコ,佐藤花子,2,19850505\n"
        "4,20260922,REC-002,調剤花子\n"
        "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_u_file = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=raw_u_file,
        ),
    )

    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    assert history.is_finalized is False
    assert res_u_file.has_pending_correction_review is False


@pytest.mark.asyncio
async def test_NSIPS数量のみ訂正_下書き薬歴あり_薬品と関連IDを保持して七日分に更新する() -> (
    None
):
    """数量だけの訂正を代替と誤認せず、処方・調剤と下書き薬歴を保持する。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    corrected = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-QUANTITY-ONLY"
    )
    original = replace(
        corrected,
        prescription=replace(
            corrected.prescription,
            rps=(replace(corrected.prescription.rps[0], dispensing_quantity=14),),
        ),
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    saved_history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    assert initial.prescription_id is not None
    assert initial.dispensing_id is not None
    prescription_id = PrescriptionId.parse(initial.prescription_id)
    dispensing_id = DispensingId.parse(initial.dispensing_id)
    before_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id, prescription_id=prescription_id
    )
    before_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    assert before_prescription is not None
    assert before_dispensing is not None
    assert before_prescription.rps[0].quantity.value == 14
    assert before_dispensing.dispensed_rps[0].quantity.value == 14
    assert saved_history.status == MedicationHistoryStatus.DRAFT

    # Act
    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, corrected)
    )

    # Assert
    assert not result.is_duplicate
    assert not result.has_pending_correction_review
    assert result.patient_id == initial.patient_id
    assert result.prescription_id == initial.prescription_id
    assert result.dispensing_id == initial.dispensing_id
    assert result.medication_history_id == str(saved_history.id.value)
    prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id, prescription_id=prescription_id
    )
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=saved_history.id
    )
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert prescription is not None
    assert dispensing is not None
    assert history is not None
    assert reception is not None
    assert history.status == MedicationHistoryStatus.DRAFT
    assert not history.has_pending_correction_review
    assert prescription.patient_id == dispensing.patient_id == saved_history.patient_id
    assert dispensing.prescription_id == history.prescription_id == prescription_id
    assert history.dispensing_id == reception.dispensing_id == dispensing_id
    assert reception.patient_id == saved_history.patient_id
    assert reception.prescription_id == prescription_id
    assert reception.medication_history_id == saved_history.id
    assert len(prescription.rps) == len(dispensing.dispensed_rps) == 1
    prescribed_rp = prescription.rps[0]
    dispensed_rp = dispensing.dispensed_rps[0]
    assert prescribed_rp.rp_number.value == dispensed_rp.rp_number.value == 1
    assert prescribed_rp.quantity.value == dispensed_rp.quantity.value == 7
    assert len(prescribed_rp.medicines) == len(dispensed_rp.medicines) == 1
    prescribed = prescribed_rp.medicines[0]
    dispensed = dispensed_rp.medicines[0]
    assert prescribed.line_number.value == dispensed.line_number.value == 1
    assert prescribed.identifier.code_type == MedicineCodeType.RECEIPT
    assert dispensed.identifier.code_type == MedicineCodeType.RECEIPT
    assert prescribed.identifier.code == MedicineCode("610406001")
    assert dispensed.identifier.code == MedicineCode("610406001")
    assert prescribed.name == dispensed.name == MedicineName("アムロジピン")
    assert dispensed.substitution is None


def _structured_bundle_for_non_prescription_correction(
    *,
    document_number: str,
    additions: tuple[NsipsAdditionInfo, ...] = (),
    dispensed_date: date = date(2026, 9, 22),
) -> NsipsBundle:
    """処方箋本体を固定し、処方箋外の受信値だけ変えるBundleを作る。"""
    return NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id="P-UFILE-STRUCTURED",
            kanji_name="訂正 花子",
            kana_name="テイセイ ハナコ",
            birth_date=date(1985, 5, 5),
            gender="2",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number=document_number,
            issued_date=date(2026, 9, 22),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日3回毎食後",
                    dispensing_quantity=7,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="アムロジピン",
                            dosage=Decimal("1"),
                            unit="錠",
                        ),
                    ),
                ),
            ),
        ),
        dispensed_date=dispensed_date,
        additions=additions,
    )


def _bundle_with_all_business_sections(document_number: str) -> NsipsBundle:
    """比較表にある業務値を全て持つBundleを組み立てる。"""
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number=document_number,
        additions=(
            NsipsAdditionInfo(code="140000110", name="加算A", points=100, quantity=1),
        ),
    )
    rp = bundle.prescription.rps[0]
    medicine = rp.medicines[0]
    return replace(
        bundle,
        patient=replace(
            bundle.patient,
            postal_code="1000001",
            address="東京都千代田区一丁目",
            phone_number="03-0000-0000",
        ),
        prescription=replace(
            bundle.prescription,
            institution_prefecture_code="13",
            department_code="01",
            department_name="内科",
            doctor_kana="サトウ イチロウ",
            rps=(
                replace(
                    rp,
                    preparation_method="unit_dose_packaged",
                    medicines=(medicine,),
                ),
            ),
            split_info=NsipsSplitInfo(
                iteration=1,
                total_split_count=2,
                split_reason="長期保存困難",
            ),
        ),
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="記号X",
            insured_number="番号789",
            branch_number="01",
            insured_type="self",
            benefit_ratio=70,
            public_payer_number_1="12345678",
            public_recipient_number_1="1234567",
            public_payer_number_2="87654321",
            public_recipient_number_2="7654321",
        ),
    )


def _replace_bundle_path(
    value: Any,
    path: tuple[str | int, ...],
    replacement: Any,
) -> Any:
    """dataclass Bundle内の一項目だけを置き換える。"""
    if not path:
        return replacement
    key, *remaining = path
    if isinstance(key, int):
        assert isinstance(value, tuple)
        values = list(value)
        values[key] = _replace_bundle_path(values[key], tuple(remaining), replacement)
        return tuple(values)
    child = getattr(value, key)
    changed = _replace_bundle_path(child, tuple(remaining), replacement)
    if isinstance(value, NsipsBundle):
        return replace(value, **{key: changed})
    return replace(value, **{key: changed})


def _command_for_reception(
    fixture: NsipsFixture,
    reception_id: ReceptionId,
    bundle: NsipsBundle,
) -> IngestNsipsCommand:
    """指定受付IDと構造化Bundleを使う取込Commandを作る。"""
    return IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(reception_id.value),
        structured_bundle=bundle,
    )


_TC57_FIELD_CHANGES: tuple[tuple[str, tuple[str | int, ...], Any], ...] = (
    ("patient.external_patient_id", ("patient", "external_patient_id"), "P-CHANGED"),
    ("patient.kanji_name", ("patient", "kanji_name"), "変更 太郎"),
    ("patient.kana_name", ("patient", "kana_name"), "ヘンコウ タロウ"),
    ("patient.birth_date", ("patient", "birth_date"), date(1980, 1, 2)),
    ("patient.gender", ("patient", "gender"), "1"),
    ("patient.postal_code", ("patient", "postal_code"), "1000002"),
    ("patient.address", ("patient", "address"), "東京都港区二丁目"),
    ("patient.phone_number", ("patient", "phone_number"), "03-1111-2222"),
    (
        "prescription.document_number",
        ("prescription", "document_number"),
        "DOC-CHANGED",
    ),
    ("prescription.issued_date", ("prescription", "issued_date"), date(2026, 9, 23)),
    ("prescription.institution_code", ("prescription", "institution_code"), "1310002"),
    (
        "prescription.institution_name",
        ("prescription", "institution_name"),
        "変更診療所",
    ),
    (
        "prescription.institution_prefecture_code",
        ("prescription", "institution_prefecture_code"),
        "14",
    ),
    ("prescription.department_code", ("prescription", "department_code"), "02"),
    ("prescription.department_name", ("prescription", "department_name"), "外科"),
    ("prescription.doctor_name", ("prescription", "doctor_name"), "山本医師"),
    ("prescription.doctor_kana", ("prescription", "doctor_kana"), "ヤマモト"),
    ("prescription.rps[0].rp_number", ("prescription", "rps", 0, "rp_number"), 2),
    (
        "prescription.rps[0].group_name",
        ("prescription", "rps", 0, "group_name"),
        "頓服",
    ),
    (
        "prescription.rps[0].instructions",
        ("prescription", "rps", 0, "instructions"),
        "1日2回食後",
    ),
    (
        "prescription.rps[0].dispensing_quantity",
        ("prescription", "rps", 0, "dispensing_quantity"),
        8,
    ),
    (
        "prescription.rps[0].preparation_method",
        ("prescription", "rps", 0, "preparation_method"),
        None,
    ),
    (
        "prescription.rps[0].medicines[0].medicine_code",
        ("prescription", "rps", 0, "medicines", 0, "medicine_code"),
        "610406002",
    ),
    (
        "prescription.rps[0].medicines[0].medicine_name",
        ("prescription", "rps", 0, "medicines", 0, "medicine_name"),
        "変更薬品",
    ),
    (
        "prescription.rps[0].medicines[0].dosage",
        ("prescription", "rps", 0, "medicines", 0, "dosage"),
        Decimal("2"),
    ),
    (
        "prescription.rps[0].medicines[0].unit",
        ("prescription", "rps", 0, "medicines", 0, "unit"),
        "包",
    ),
    (
        "prescription.split_info.iteration",
        ("prescription", "split_info", "iteration"),
        2,
    ),
    (
        "prescription.split_info.total_split_count",
        ("prescription", "split_info", "total_split_count"),
        3,
    ),
    (
        "prescription.split_info.split_reason",
        ("prescription", "split_info", "split_reason"),
        "別の分割理由",
    ),
    ("dispensed_date", ("dispensed_date",), date(2026, 9, 23)),
    ("insurance.insurer_number", ("insurance", "insurer_number"), "138002"),
    ("insurance.insured_symbol", ("insurance", "insured_symbol"), "記号Y"),
    ("insurance.insured_number", ("insurance", "insured_number"), "番号790"),
    ("insurance.branch_number", ("insurance", "branch_number"), "02"),
    ("insurance.insured_type", ("insurance", "insured_type"), "dependent"),
    ("insurance.benefit_ratio", ("insurance", "benefit_ratio"), 60),
    (
        "insurance.public_payer_number_1",
        ("insurance", "public_payer_number_1"),
        "22345678",
    ),
    (
        "insurance.public_recipient_number_1",
        ("insurance", "public_recipient_number_1"),
        "2234567",
    ),
    (
        "insurance.public_payer_number_2",
        ("insurance", "public_payer_number_2"),
        "97654321",
    ),
    (
        "insurance.public_recipient_number_2",
        ("insurance", "public_recipient_number_2"),
        "8765432",
    ),
    ("additions[0].code", ("additions", 0, "code"), "140000210"),
    ("additions[0].name", ("additions", 0, "name"), "加算B"),
    ("additions[0].points", ("additions", 0, "points"), 200),
    ("additions[0].quantity", ("additions", 0, "quantity"), 2),
)

_TC66_PROFILE_FIELD_CHANGES = tuple(
    item
    for item in _TC57_FIELD_CHANGES
    if item[0].startswith("patient.") and item[0] != "patient.external_patient_id"
)


@pytest.mark.asyncio
async def test_tc51_初回U相当の未登録受付は通常の初回取込になる() -> None:
    """ファイル種別に関係なく未登録受付IDなら初回登録経路を通る。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC51-FIRST-U",
    )

    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, bundle)
    )

    assert result.is_new_patient is True
    assert result.is_duplicate is False
    assert result.has_pending_correction_review is False
    assert result.prescription_id is not None
    assert result.dispensing_id is not None
    assert result.medication_history_id is None
    assert fixture.medication_history_repo.items == {}
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.patient_id.value == PatientId.parse(result.patient_id).value
    assert reception.latest_fingerprint


@pytest.mark.asyncio
async def test_tc52_同じ受付Bundleの再送は受付記録も副作用も重ねない() -> None:
    """同一受付の再送は永続化されたハッシュ値で冪等になる。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    command = _command_for_reception(
        fixture,
        reception_id,
        _structured_bundle_for_non_prescription_correction(
            document_number="DOC-TC52-IDEMPOTENT",
        ),
    )

    first = await execute_structured_test_command(fixture, command)
    counts_after_first = (
        len(fixture.patient_repo.items),
        len(fixture.patient_external_id_repo.items),
        len(fixture.prescription_repo.items),
        len(fixture.dispensing_repo.items),
        len(fixture.medication_history_repo.items),
        len(fixture.coverage_selection_repo.items),
        sum(
            len(patient.profile_history)
            for patient in fixture.patient_repo.items.values()
        ),
    )
    replay = await execute_structured_test_command(fixture, command)
    counts_after_replay = (
        len(fixture.patient_repo.items),
        len(fixture.patient_external_id_repo.items),
        len(fixture.prescription_repo.items),
        len(fixture.dispensing_repo.items),
        len(fixture.medication_history_repo.items),
        len(fixture.coverage_selection_repo.items),
        sum(
            len(patient.profile_history)
            for patient in fixture.patient_repo.items.values()
        ),
    )

    assert replay.is_duplicate is True
    assert replay.prescription_id == first.prescription_id
    assert counts_after_replay == counts_after_first
    assert len(fixture.reception_repo.items) == 1


@pytest.mark.asyncio
async def test_tc53_受付訂正の同一再送は訂正履歴を一度だけ記録する() -> None:
    """訂正Bundleは差分として追記し、同じ訂正の再送を重ねない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC53-CORRECTION",
    )
    corrected = replace(
        original,
        prescription=replace(
            original.prescription,
            institution_name="訂正診療所",
        ),
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    corrected_command = _command_for_reception(fixture, reception_id, corrected)

    first_correction = await execute_structured_test_command(fixture, corrected_command)
    replayed_correction = await execute_structured_test_command(
        fixture, corrected_command
    )

    assert first_correction.is_duplicate is False
    assert replayed_correction.is_duplicate is True
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert len(reception.correction_history) == 1
    assert "prescription.institution_name" in {
        field.value for field in reception.correction_history[0].changed_fields
    }


@pytest.mark.asyncio
async def test_tc56_header_versionだけの変更は業務差分にしない() -> None:
    """形式メタデータだけが異なる場合は業務上の重複として扱う。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC56-HEADER",
    )
    changed_header = replace(original, header_version="metadata-only-change")
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )

    replay = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, changed_header)
    )

    assert replay.is_duplicate is True
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "path", "changed_value"),
    _TC57_FIELD_CHANGES,
    ids=tuple(item[0] for item in _TC57_FIELD_CHANGES),
)
async def test_tc57_NsipsBundleの全業務フィールド単独差分を検出する(
    field_name: str,
    path: tuple[str | int, ...],
    changed_value: Any,
) -> None:
    """業務フィールド単独差分を検出し、患者同一性を変える差分だけ拒否する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC57-ALL-FIELDS",
    )
    changed = _replace_bundle_path(original, path, changed_value)
    assert isinstance(changed, NsipsBundle)

    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    if field_name == "patient.external_patient_id":
        # Arrange: 関連薬歴・プロフィールと受付の訂正履歴・頭書きを用意する。
        await _save_history_after_pharmacist_writing(
            fixture, reception_id=reception_id, ingest_result=initial
        )
        legitimate = replace(
            original, patient=replace(original.patient, address="東京都品川区三丁目")
        )
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, legitimate)
        )
        patient_id = PatientId.parse(initial.patient_id)
        patient = fixture.patient_repo.items[patient_id]
        await fixture.patient_repo.save(
            patient.change_heading(
                PatientHeadingContent(
                    summary=PatientHeadingText("元患者の継続申し送り"), notes=None
                ),
                expected_revision=0,
                person_id=AccountPersonId.generate(),
                account_id=UserAccountId.generate(),
                recorded_at=fixture.clock.now(),
            )
        )
        assert patient.profile_history
        changed = _replace_bundle_path(legitimate, path, changed_value)
        assert isinstance(changed, NsipsBundle)
        before = _snapshot_saved_state(fixture)

        # Act
        with pytest.raises(NsipsPatientIdentityConflictError):
            await execute_structured_test_command(
                fixture, _command_for_reception(fixture, reception_id, changed)
            )

        # Assert
        assert _snapshot_saved_state(fixture) == before
        return

    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, changed)
    )

    assert result.is_duplicate is False
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert any(
        field_name in {field.value for field in correction.changed_fields}
        for correction in reception.correction_history
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "path", "changed_value"),
    (
        ("patient.address", ("patient", "address"), None),
        ("patient.phone_number", ("patient", "phone_number"), None),
        ("prescription.split_info", ("prescription", "split_info"), None),
        ("insurance", ("insurance",), None),
        ("additions", ("additions",), ()),
        ("prescription.rps", ("prescription", "rps"), ()),
        (
            "prescription.rps[0].medicines",
            ("prescription", "rps", 0, "medicines"),
            (),
        ),
    ),
    ids=(
        "住所欠落",
        "電話欠落",
        "分割情報削除",
        "保険情報欠落",
        "加算削除",
        "Rp削除",
        "薬品明細削除",
    ),
)
async def test_tc58_任意値と要素の欠落も受付差分として記録する(
    field_name: str,
    path: tuple[str | int, ...],
    changed_value: Any,
) -> None:
    """受信値の欠落を黙殺せず、患者マスター値は削除しない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC58-MISSING",
    )
    if field_name == "prescription.rps":
        original_rp = original.prescription.rps[0]
        second_rp = replace(original_rp, rp_number=2, group_name="頓服")
        original = replace(
            original,
            prescription=replace(
                original.prescription,
                rps=(original_rp, second_rp),
            ),
        )
        changed_value = (original_rp,)
    elif field_name == "prescription.rps[0].medicines":
        original_rp = original.prescription.rps[0]
        original_medicine = original_rp.medicines[0]
        second_medicine = replace(original_medicine, dosage=Decimal("2"))
        original = replace(
            original,
            prescription=replace(
                original.prescription,
                rps=(
                    replace(
                        original_rp,
                        medicines=(original_medicine, second_medicine),
                    ),
                ),
            ),
        )
        changed_value = (original_medicine,)
    changed = _replace_bundle_path(original, path, changed_value)
    assert isinstance(changed, NsipsBundle)
    first = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )

    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, changed)
    )

    assert result.is_duplicate is False
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(first.patient_id),
    )
    assert patient is not None
    assert patient.address is not None
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert field_name in {
        field.value for field in reception.correction_history[0].changed_fields
    }


@pytest.mark.asyncio
async def test_tc58_任意項目やコレクションの追加も差分として保存する() -> None:
    """前回なかったプロフィール・保険・Rp・加算の追加を検出する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC58-ADDED"
    )
    original_rp = original.prescription.rps[0]
    original_medicine = original_rp.medicines[0]
    changed = replace(
        original,
        patient=replace(original.patient, address="東京都中央区三丁目"),
        prescription=replace(
            original.prescription,
            split_info=NsipsSplitInfo(
                iteration=1,
                total_split_count=2,
                split_reason="分割交付",
            ),
            rps=(
                original_rp,
                replace(
                    original_rp,
                    rp_number=2,
                    group_name="頓服",
                    medicines=(original_medicine,),
                ),
            ),
        ),
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="追加記号",
            insured_number="追加番号",
            insured_type="self",
            benefit_ratio=70,
        ),
        additions=(
            NsipsAdditionInfo(
                code="140000110",
                name="加算A",
                points=100,
                quantity=1,
            ),
        ),
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )

    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, changed)
    )

    assert result.is_duplicate is False
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    fields = {field.value for field in reception.correction_history[0].changed_fields}
    assert "patient.address" in fields
    assert "prescription.split_info" in fields
    assert "prescription.rps" in fields
    assert "insurance" in fields
    assert "additions" in fields


@pytest.mark.asyncio
async def test_tc58_Rp薬品と加算の並べ替えは順序差分になる() -> None:
    """順序が業務入力の一部となるコレクションを並べ替えとして記録する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC58-ORDER",
    )
    first_rp = original.prescription.rps[0]
    first_medicine = first_rp.medicines[0]
    second_medicine = replace(
        first_medicine,
        dosage=Decimal("2"),
    )
    second_rp = replace(
        first_rp,
        rp_number=2,
        group_name="頓服",
        medicines=(second_medicine,),
    )
    first_addition = original.additions[0]
    second_addition = replace(first_addition, code="140000210", name="加算B")
    original = replace(
        original,
        prescription=replace(
            original.prescription,
            rps=(first_rp, second_rp),
        ),
        additions=(first_addition, second_addition),
    )
    reordered = replace(
        original,
        prescription=replace(
            original.prescription,
            rps=(second_rp, first_rp),
        ),
        additions=(second_addition, first_addition),
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )

    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, reordered)
    )

    assert result.is_duplicate is False
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    changed_fields = reception.correction_history[0].changed_fields
    assert any(field.value.startswith("prescription.rps[") for field in changed_fields)
    assert any(field.value.startswith("additions[") for field in changed_fields)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "path", "changed_value"),
    _TC66_PROFILE_FIELD_CHANGES,
    ids=tuple(item[0] for item in _TC66_PROFILE_FIELD_CHANGES),
)
async def test_tc66_別受付で変わった患者プロフィールを受信履歴へ残す(
    field_name: str,
    path: tuple[str | int, ...],
    changed_value: Any,
) -> None:
    """A相当の別受付でもPatientを保ち受信した変更プロフィールを記録する。"""
    fixture = await create_fixture()
    original = _bundle_with_all_business_sections(
        document_number=f"DOC-TC66-{field_name}",
    )
    changed = _replace_bundle_path(original, path, changed_value)
    assert isinstance(changed, NsipsBundle)
    changed = replace(
        changed,
        prescription=replace(
            changed.prescription,
            document_number=f"DOC-TC66-SECOND-{field_name}",
        ),
    )
    first = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, ReceptionId.generate(), original),
    )

    second = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, ReceptionId.generate(), changed),
    )

    assert second.patient_id == first.patient_id
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(first.patient_id),
    )
    assert patient is not None
    assert len(patient.profile_history) == 1
    profile_change = patient.profile_history[0]
    assert field_name in profile_change.changed_fields
    assert profile_change.store_id == fixture.store_id
    assert profile_change.external_patient_id is not None
    assert (
        profile_change.external_patient_id.value == original.patient.external_patient_id
    )
    assert profile_change.recorded_at == fixture.clock.now()
    received_profile = profile_change.received_profile
    assert received_profile is not None
    assert received_profile.address is not None
    assert received_profile.address.value == changed.patient.address
    assert (
        received_profile.birth_date is not None
        and received_profile.birth_date.value == changed.patient.birth_date
    )
    before_profile = profile_change.before_profile
    applied_profile = profile_change.applied_profile
    assert before_profile is not None
    assert applied_profile is not None
    if field_name == "patient.kanji_name":
        assert before_profile.names.kanji.full_name == original.patient.kanji_name
        assert applied_profile.names.kanji.full_name == changed.patient.kanji_name
        assert patient.names.kanji.full_name == changed.patient.kanji_name
    elif field_name == "patient.kana_name":
        assert before_profile.names.kana.full_name == original.patient.kana_name
        assert applied_profile.names.kana.full_name == changed.patient.kana_name
        assert patient.names.kana.full_name == changed.patient.kana_name
    elif field_name == "patient.birth_date":
        assert before_profile.birth_date is not None
        assert before_profile.birth_date.value == original.patient.birth_date
        assert applied_profile.birth_date is not None
        assert applied_profile.birth_date.value == changed.patient.birth_date
        assert patient.birth_date is not None
        assert patient.birth_date.value == changed.patient.birth_date
    elif field_name == "patient.gender":
        assert before_profile.gender is not None
        assert before_profile.gender.value == original.patient.gender
        assert applied_profile.gender is not None
        assert applied_profile.gender.value == changed.patient.gender
        assert patient.gender is not None
        assert patient.gender.value == changed.patient.gender
    elif field_name == "patient.postal_code":
        assert before_profile.postal_code is not None
        assert before_profile.postal_code.value == original.patient.postal_code
        assert applied_profile.postal_code is not None
        assert applied_profile.postal_code.value == changed.patient.postal_code
        assert patient.postal_code is not None
        assert patient.postal_code.value == changed.patient.postal_code
    elif field_name == "patient.address":
        assert before_profile.address is not None
        assert before_profile.address.value == original.patient.address
        assert applied_profile.address is not None
        assert applied_profile.address.value == changed.patient.address
        assert patient.address is not None
        assert patient.address.value == changed.patient.address
    elif field_name == "patient.phone_number":
        assert before_profile.phone_number is not None
        assert before_profile.phone_number.value == original.patient.phone_number
        assert applied_profile.phone_number is not None
        assert applied_profile.phone_number.value == changed.patient.phone_number
        assert patient.phone_number is not None
        assert patient.phone_number.value == changed.patient.phone_number
    assert getattr(second, "patient_profile_updated_fields", ()) == (field_name,)
    assert second.patient_attribute_conflicts == ()
    assert second.has_pending_correction_review is False


@pytest.mark.asyncio
async def test_tc67_AからB1_C_B2へ戻る訂正を履歴化し完全再送だけを冪等にする() -> None:
    """受付受信順を履歴へ残し、同じ値の再登場を過去履歴で抑止しない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(document_number="DOC-TC67-SAME")
    profile_b = replace(
        original,
        patient=replace(original.patient, address="東京都新宿区一丁目"),
    )
    profile_c = replace(
        profile_b,
        patient=replace(profile_b.patient, address="東京都渋谷区二丁目"),
    )
    profile_b2 = replace(
        profile_c,
        patient=replace(profile_c.patient, address="東京都新宿区一丁目"),
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    for incoming in (profile_b, profile_c, profile_b2):
        result = await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, incoming)
        )
        assert result.is_duplicate is False
        assert result.patient_attribute_conflicts == ()
        assert result.has_pending_correction_review is False
        assert getattr(result, "patient_profile_updated_fields", ()) == (
            "patient.address",
        )

    replay = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, profile_b2)
    )
    assert replay.is_duplicate is True

    identifier = await fixture.patient_external_id_repo.get_active_by_source(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        system_name=ExternalSystemName("recept"),
        external_patient_id=ExternalPatientId(original.patient.external_patient_id),
    )
    assert identifier is not None
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=identifier.patient_id,
    )
    assert patient is not None
    changes = [
        change
        for change in patient.profile_history
        if "patient.address" in change.changed_fields
    ]
    addresses: list[str] = []
    for change in changes:
        assert change.received_profile is not None
        assert change.received_profile.address is not None
        addresses.append(change.received_profile.address.value)
    assert addresses == [
        "東京都新宿区一丁目",
        "東京都渋谷区二丁目",
        "東京都新宿区一丁目",
    ]
    assert patient.address is not None
    assert patient.address.value == "東京都新宿区一丁目"

    # Patientマスターが受付値から後で手動更新された状態で、患者項目を変えず
    # 処方だけを訂正する。古い受信値でマスターを戻してはならない。
    await fixture.patient_repo.save(
        replace(patient, address=PatientAddress("東京都品川区三丁目"))
    )
    prescription_only = replace(
        profile_b2,
        prescription=replace(
            profile_b2.prescription,
            doctor_name="訂正された処方医",
        ),
    )
    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, prescription_only)
    )
    assert result.patient_attribute_conflicts == ()
    assert getattr(result, "patient_profile_updated_fields", ()) == ()
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=identifier.patient_id,
    )
    assert patient is not None
    assert patient.address is not None
    assert patient.address.value == "東京都品川区三丁目"


def _snapshot_saved_state(
    fixture: NsipsFixture,
) -> tuple[dict[object, dict[str, Any]], ...]:
    """IDによる集約の等値判定を避け、全保存値を独立して取得する。"""
    return tuple(
        {key: asdict(value) for key, value in repository.items.items()}
        for repository in (
            fixture.patient_repo,
            fixture.patient_external_id_repo,
            fixture.reception_repo,
            fixture.prescription_repo,
            fixture.dispensing_repo,
            fixture.medication_history_repo,
            fixture.patient_coverage_repo,
            fixture.coverage_selection_repo,
        )
    )


@pytest.mark.asyncio
async def test_取込_外部患者IDと属性同時変更_拒否し保存状態を維持する() -> None:
    """別人の属性を受理せず、既存の履歴と集約間参照をすべて保持する。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-IDENTITY-CONFLICT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    before = _snapshot_saved_state(fixture)
    conflicting = replace(
        legitimate,
        patient=replace(
            legitimate.patient,
            external_patient_id="P-OTHER-PERSON",
            kanji_name="別人 花子",
            kana_name="ベツジン ハナコ",
            birth_date=date(1980, 1, 2),
            gender="1",
            postal_code="1000002",
            address="東京都港区二丁目",
            phone_number="03-1111-2222",
        ),
    )

    for _ in range(2):
        # Act: 初回拒否と同じ入力の再送を確認する。
        with pytest.raises(NsipsPatientIdentityConflictError):
            await execute_structured_test_command(
                fixture, _command_for_reception(fixture, reception_id, conflicting)
            )

        # Assert
        assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_tc68_取込_外部患者ID単独変更_拒否し保存状態を維持する() -> None:
    """IDだけ変わる訂正を拒否し、元患者の履歴と全保存値を維持する。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC68-EXTERNAL-ID"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate,
        patient=replace(legitimate.patient, external_patient_id="P-TC68-CHANGED"),
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_取込_同一患者の別有効IDで再送_受付指紋の元IDを基準に拒否する() -> None:
    """同じ内部患者の有効リンクでも保存済み受付の患者IDを置き換えない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-FINGERPRINT-IDENTITY"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    assert any(
        path.value == "patient.external_patient_id"
        for path, _ in reception.field_fingerprints
    )
    original_link = next(iter(fixture.patient_external_id_repo.items.values()))
    alternate_link = PatientExternalIdentifier.create(
        corporate_id=fixture.corporate_id,
        store_id=original_link.store_id,
        patient_id=patient_id,
        system_name=original_link.system_name,
        external_patient_id=ExternalPatientId("P-ALTERNATE-ACTIVE"),
    )
    await fixture.patient_external_id_repo.save(alternate_link)
    active_link = await fixture.patient_external_id_repo.get_active_by_source(
        corporate_id=fixture.corporate_id,
        store_id=alternate_link.store_id,
        system_name=alternate_link.system_name,
        external_patient_id=alternate_link.external_patient_id,
    )
    assert active_link is not None
    assert active_link.patient_id == patient_id
    assert active_link.is_active
    assert len(fixture.patient_external_id_repo.items) == 2
    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate,
        patient=replace(
            legitimate.patient,
            external_patient_id=alternate_link.external_patient_id.value,
        ),
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_tc69_患者プロフィール受信Noneで既存値や履歴を消さない() -> None:
    """患者情報の受信欠損をマスターからの削除指示として扱わない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC69-NONE-INITIAL",
    )
    first = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, reception_id, original),
    )
    received_none = replace(
        original,
        prescription=replace(
            original.prescription,
            document_number="DOC-TC69-NONE-SECOND",
        ),
        patient=replace(
            original.patient,
            gender=None,
            postal_code=None,
            address=None,
            phone_number=None,
        ),
    )

    second = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, received_none)
    )
    replay = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, received_none)
    )

    assert second.patient_id == first.patient_id
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(first.patient_id),
    )
    assert patient is not None
    assert (
        patient.gender is not None and patient.gender.value == original.patient.gender
    )
    assert (
        patient.postal_code is not None
        and patient.postal_code.value == original.patient.postal_code
    )
    assert (
        patient.address is not None
        and patient.address.value == original.patient.address
    )
    assert (
        patient.phone_number is not None
        and patient.phone_number.value == original.patient.phone_number
    )
    assert getattr(second, "patient_profile_updated_fields", ()) == ()
    assert second.patient_attribute_conflicts == (
        "gender",
        "postal_code",
        "address",
        "phone_number",
    )
    assert second.has_pending_correction_review is True
    assert replay.is_duplicate is True
    none_changes = [
        change
        for change in patient.profile_history
        if any(
            field in change.changed_fields
            for field in (
                "patient.gender",
                "patient.postal_code",
                "patient.address",
                "patient.phone_number",
            )
        )
    ]
    assert len(none_changes) == 1
    received_none_profile = none_changes[0].received_profile
    assert received_none_profile is not None
    assert received_none_profile.gender is None
    assert received_none_profile.postal_code is None
    assert received_none_profile.address is None
    assert received_none_profile.phone_number is None
    assert none_changes[0].before_profile is not None
    assert none_changes[0].applied_profile is not None
    assert none_changes[0].applied_profile.address is not None
    assert none_changes[0].applied_profile.address.value == original.patient.address


def _bundle_with_patient_difference(
    bundle: NsipsBundle, field_name: str
) -> NsipsBundle:
    """患者識別・属性のうち指定した1項目だけを変更したBundleを返す。"""
    if field_name == "external_patient_id":
        patient = replace(bundle.patient, external_patient_id="P-UFILE-CHANGED")
    elif field_name == "kanji_name":
        patient = replace(bundle.patient, kanji_name="変更 花子")
    elif field_name == "kana_name":
        patient = replace(bundle.patient, kana_name="ヘンコウ ハナコ")
    elif field_name == "birth_date":
        patient = replace(bundle.patient, birth_date=date(1985, 5, 6))
    else:
        raise AssertionError(f"未対応のテスト項目: {field_name}")
    return replace(bundle, patient=patient)


def _bundle_with_prescription_metadata_difference(
    bundle: NsipsBundle, field_name: str
) -> NsipsBundle:
    """処方メタデータのうち指定した1項目だけを変更したBundleを返す。"""
    prescription = bundle.prescription
    rp = prescription.rps[0]
    medicine = rp.medicines[0]

    if field_name == "institution_code":
        prescription = replace(prescription, institution_code="1310002")
    elif field_name == "institution_name":
        prescription = replace(prescription, institution_name="変更診療所")
    elif field_name == "department_code":
        prescription = replace(prescription, department_code="02")
    elif field_name == "department_name":
        prescription = replace(prescription, department_name="変更科")
    elif field_name == "doctor_name":
        prescription = replace(prescription, doctor_name="変更医師")
    elif field_name == "split_info":
        prescription = replace(
            prescription,
            split_info=NsipsSplitInfo(
                iteration=1,
                total_split_count=2,
                split_reason="長期保存困難",
            ),
        )
    elif field_name == "instructions":
        prescription = replace(
            prescription,
            rps=(replace(rp, instructions="1日2回食後"),),
        )
    elif field_name == "preparation_method":
        prescription = replace(
            prescription,
            rps=(replace(rp, preparation_method="unit_dose_packaged"),),
        )
    elif field_name == "medicine_name":
        prescription = replace(
            prescription,
            rps=(
                replace(
                    rp,
                    medicines=(replace(medicine, medicine_name="変更薬品名"),),
                ),
            ),
        )
    elif field_name == "unit":
        prescription = replace(
            prescription,
            rps=(replace(rp, medicines=(replace(medicine, unit="包"),)),),
        )
    else:
        raise AssertionError(f"未対応のテスト項目: {field_name}")

    return replace(bundle, prescription=prescription)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name",
    ("external_patient_id", "kanji_name", "kana_name", "birth_date"),
)
async def test_tc46_取込_患者プロフィール差分_同一IDは反映し外部ID変更は拒否する(
    field_name: str,
) -> None:
    """同一患者の属性訂正は反映し、外部患者IDの変更は保存前に拒否する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC46-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    saved_history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    patient_id = PatientId.parse(initial.patient_id)
    original_patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert original_patient is not None
    original_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert len(original_links) == 1
    before = _snapshot_saved_state(fixture)

    if field_name == "external_patient_id":
        # Arrange: 空でない訂正履歴と頭書きを持つ患者へのID単独変更。
        legitimate = replace(
            original_bundle,
            patient=replace(original_bundle.patient, address="東京都品川区三丁目"),
        )
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, legitimate)
        )
        patient = fixture.patient_repo.items[patient_id]
        await fixture.patient_repo.save(
            patient.change_heading(
                PatientHeadingContent(
                    summary=PatientHeadingText("元患者の継続申し送り"), notes=None
                ),
                expected_revision=0,
                person_id=AccountPersonId.generate(),
                account_id=UserAccountId.generate(),
                recorded_at=fixture.clock.now(),
            )
        )
        assert patient.profile_history
        before = _snapshot_saved_state(fixture)

        # Act
        with pytest.raises(NsipsPatientIdentityConflictError):
            await execute_structured_test_command(
                fixture,
                _command_for_reception(
                    fixture,
                    reception_id,
                    _bundle_with_patient_difference(legitimate, field_name),
                ),
            )

        # Assert
        assert _snapshot_saved_state(fixture) == before
        return

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=_bundle_with_patient_difference(
                original_bundle, field_name
            ),
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.medication_history_id == str(saved_history.id.value)
    history_id = saved_history.id
    corrected_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert corrected_history is not None
    updated_patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert updated_patient is not None
    assert corrected.has_pending_correction_review is False
    assert corrected.patient_attribute_conflicts == ()
    assert corrected_history.external_corrections == ()
    assert (
        len(updated_patient.profile_history)
        == len(original_patient.profile_history) + 1
    )
    assert updated_patient.profile_history[:-1] == original_patient.profile_history
    assert corrected.patient_id == initial.patient_id
    assert corrected_history.patient_id == patient_id
    after = _snapshot_saved_state(fixture)
    for index in (2, 3, 4, 5):
        assert after[index].keys() == before[index].keys()
        for identifier, saved in before[index].items():
            for reference in (
                "patient_id",
                "prescription_id",
                "dispensing_id",
                "medication_history_id",
            ):
                if reference in saved:
                    assert after[index][identifier][reference] == saved[reference]
    assert getattr(corrected, "patient_profile_updated_fields", ()) == (
        f"patient.{field_name}",
    )
    if field_name == "kanji_name":
        assert updated_patient.names.kanji.full_name == "変更 花子"
    elif field_name == "kana_name":
        assert updated_patient.names.kana.full_name == "ヘンコウ ハナコ"
    elif field_name == "birth_date":
        assert updated_patient.birth_date is not None
        assert updated_patient.birth_date.value == date(1985, 5, 6)
    assert updated_patient.profile_history[-1].changed_fields == (
        f"patient.{field_name}",
    )

    unchanged_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert tuple(item.external_patient_id.value for item in unchanged_links) == tuple(
        item.external_patient_id.value for item in original_links
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name",
    (
        "institution_code",
        "institution_name",
        "department_code",
        "department_name",
        "doctor_name",
        "split_info",
        "instructions",
        "preparation_method",
        "medicine_name",
        "unit",
    ),
)
async def test_tc47_処方メタデータ差分は重複扱いせず訂正を要確認にする(
    field_name: str,
) -> None:
    """処方メタデータ差分を検知し、原処方・確定薬歴へ自動反映しない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC47-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history_id = history.id
    finalized_history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(finalized_history)
    dispensing_id = history.dispensing_id
    assert dispensing_id is not None
    original_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert original_dispensing is not None
    original_prescription = await fixture.prescription_repo.get_by_document_number(
        corporate_id=fixture.corporate_id,
        document_number=PrescriptionDocumentNumber(
            original_bundle.prescription.document_number
        ),
    )
    assert original_prescription is not None

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=_bundle_with_prescription_metadata_difference(
                original_bundle, field_name
            ),
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.has_pending_correction_review is True
    updated_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id,
        prescription_id=original_prescription.id,
    )
    assert updated_prescription is not None
    assert (
        updated_prescription.medical_institution
        == original_prescription.medical_institution
    )
    assert updated_prescription.department == original_prescription.department
    assert updated_prescription.prescriber == original_prescription.prescriber
    assert updated_prescription.rps == original_prescription.rps
    updated_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=original_dispensing.id,
    )
    assert updated_dispensing is not None
    assert updated_dispensing.dispensed_rps == original_dispensing.dispensed_rps
    assert updated_dispensing.split_reason == original_dispensing.split_reason
    assert updated_dispensing.total_split_count == original_dispensing.total_split_count
    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert reloaded_history is not None
    assert reloaded_history.soap == finalized_history.soap
    assert reloaded_history.is_finalized is True
    assert reloaded_history.has_pending_correction_review is True
    assert field_name in (reloaded_history.external_corrections[-1].details or "")


@pytest.mark.asyncio
async def test_tc49_訂正証跡の時刻は必須の注入Clockから取得する() -> None:
    """訂正日時に注入Clockを使い、Applicationの実時刻フォールバックを許さない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    clock_parameter = inspect.signature(type(fixture.use_case).__init__).parameters[
        "clock"
    ]
    assert clock_parameter.default is inspect.Parameter.empty

    original = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-CLOCK",
        additions=(NsipsAdditionInfo(code="140000110", name="加算A", points=100),),
    )
    corrected_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-CLOCK",
        additions=(NsipsAdditionInfo(code="140000210", name="加算B", points=200),),
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original,
        ),
    )
    saved_history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=corrected_bundle,
        ),
    )
    assert corrected.has_pending_correction_review is True
    assert corrected.medication_history_id == str(saved_history.id.value)
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=saved_history.id,
    )
    assert history is not None
    assert history.external_corrections[-1].corrected_at.value == fixture.clock.now()


@pytest.mark.asyncio
async def test_tc33_加算だけが変わった訂正を単純再送として捨てない() -> None:
    """処方薬が同じでも加算差分は重複応答で消さない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-ADDITION",
        additions=(NsipsAdditionInfo(code="140000110", name="加算A", points=100),),
    )
    corrected_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-ADDITION",
        additions=(NsipsAdditionInfo(code="140000210", name="加算B", points=200),),
    )

    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=corrected_bundle,
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.prescription_id == initial.prescription_id


@pytest.mark.asyncio
async def test_tc34_調剤日だけが変わった訂正を単純再送として捨てない() -> None:
    """同一処方箋番号でも調剤日の差分を重複扱いで隠さない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-DISPENSED-DATE",
        dispensed_date=date(2026, 9, 22),
    )
    corrected_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-DISPENSED-DATE",
        dispensed_date=date(2026, 9, 23),
    )

    await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=corrected_bundle,
        ),
    )

    assert corrected.is_duplicate is False


@pytest.mark.asyncio
async def test_tc35_確定薬歴の加算訂正で原本を保持して要確認にする() -> None:
    """確定後の加算差分は原本を書き換えず訂正確認として残す。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-FINALIZED-ADDITION",
        additions=(NsipsAdditionInfo(code="140000110", name="加算A", points=100),),
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history_id = history.id
    finalized = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(finalized)

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=_structured_bundle_for_non_prescription_correction(
                document_number="DOC-UFILE-FINALIZED-ADDITION",
                additions=(
                    NsipsAdditionInfo(code="140000210", name="加算B", points=200),
                ),
            ),
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.has_pending_correction_review is True
    reloaded = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert reloaded is not None
    assert reloaded.soap == finalized.soap
    assert reloaded.finalized_at == finalized.finalized_at
    assert reloaded.finalized_by == finalized.finalized_by
    assert reloaded.billing_additions == finalized.billing_additions
    assert reloaded.is_finalized is True
    assert len(reloaded.external_corrections) == 1


@pytest.mark.asyncio
async def test_tc36_下書き薬歴への未対応加算訂正を重複成功にしない() -> None:
    """DRAFTへの未対応加算差分を、無変更の重複応答として黙殺しない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=_structured_bundle_for_non_prescription_correction(
                document_number="DOC-UFILE-DRAFT-ADDITION",
                additions=(
                    NsipsAdditionInfo(code="140000110", name="加算A", points=100),
                ),
            ),
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history_id = history.id

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=_structured_bundle_for_non_prescription_correction(
                document_number="DOC-UFILE-DRAFT-ADDITION",
                additions=(
                    NsipsAdditionInfo(code="140000210", name="加算B", points=200),
                ),
            ),
        ),
    )

    assert corrected.is_duplicate is False
    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert reloaded_history is not None
    assert reloaded_history.is_finalized is False
    if corrected.has_pending_correction_review:
        assert reloaded_history.billing_additions[0].code.value == "140000110"
    else:
        assert reloaded_history.billing_additions[0].code.value == "140000210"


@pytest.mark.asyncio
async def test_tc59_剤数量と保険欠落が同時に変わる場合は自動訂正しない() -> None:
    """複合訂正は薬歴を作らず、受付の受信・訂正履歴だけに保管する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial_bundle = _bundle_with_all_business_sections(
        document_number="DOC-TC59-COMBINED-DIFFERENCE",
    )
    initial = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, reception_id, initial_bundle),
    )
    assert initial.medication_history_id is None
    assert fixture.medication_history_repo.items == {}

    assert initial.prescription_id is not None
    assert initial.dispensing_id is not None
    prescription_id = PrescriptionId.parse(initial.prescription_id)
    dispensing_id = DispensingId.parse(initial.dispensing_id)
    original_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id,
        prescription_id=prescription_id,
    )
    assert original_prescription is not None
    original_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert original_dispensing is not None
    initial_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert initial_reception is not None
    assert initial_reception.source_data is not None

    original_rp = initial_bundle.prescription.rps[0]
    corrected_bundle = replace(
        initial_bundle,
        prescription=replace(
            initial_bundle.prescription,
            rps=(replace(original_rp, dispensing_quantity=8),),
        ),
        insurance=None,
    )

    corrected = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, reception_id, corrected_bundle),
    )

    assert corrected.is_duplicate is False
    assert corrected.has_pending_correction_review is True
    assert corrected.medication_history_id is None
    assert fixture.medication_history_repo.items == {}
    reloaded_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id,
        prescription_id=prescription_id,
    )
    assert reloaded_prescription == original_prescription
    reloaded_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert reloaded_dispensing == original_dispensing
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.medication_history_id is None
    assert reception.source_data is not None
    assert reception.source_data_history == (initial_reception.source_data,)
    assert (
        reception.source_data.bundle_json != initial_reception.source_data.bundle_json
    )
    assert {
        field.value for field in reception.correction_history[-1].changed_fields
    } >= {"insurance", "prescription.rps[0].dispensing_quantity"}


@pytest.mark.asyncio
async def test_issue36_tc33_U再取込の加算比較は新しいFOLLOW_UPではなくINITIALを使う() -> (
    None
):
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    addition_info = NsipsAdditionInfo(
        code="140000110", name="初回算定", points=100, quantity=1
    )
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-ISSUE36-UFILE",
        additions=(addition_info,),
    )
    ingested = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    assert ingested.patient_id is not None
    assert ingested.prescription_id is not None
    assert ingested.dispensing_id is not None
    prescription_id = PrescriptionId.parse(ingested.prescription_id)
    dispensing_id = DispensingId.parse(ingested.dispensing_id)
    prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id,
        prescription_id=prescription_id,
    )
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=dispensing_id,
    )
    assert prescription is not None
    assert dispensing is not None
    initial = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=PatientId.parse(ingested.patient_id),
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            counselor_id=fixture.pharmacist_id,
            billing_additions=(
                BillingAddition(
                    code=BillingAdditionCode(addition_info.code),
                    name=BillingAdditionName(addition_info.name),
                    points=addition_info.points,
                    quantity=addition_info.quantity,
                ),
            ),
        )
    )
    follow_up = create_independent_follow_up_record(
        initial,
        store_id=StoreId.generate(),
        counseled_at=fixture.clock.now().replace(day=25),
        finalized=True,
    )
    await fixture.medication_history_repo.save(initial)
    await fixture.medication_history_repo.save(follow_up)
    assert follow_up.dispensing_id is None
    assert follow_up.prescription_id is None

    difference = await fixture.use_case._detect_bundle_differences(
        corporate_id=fixture.corporate_id,
        existing=prescription,
        bundle=bundle,
        patient_attribute_conflicts=(),
    )

    assert difference is None


@pytest.mark.asyncio
async def test_取込_患者ID指紋欠損の完全重複で別患者リンク_拒否し保存状態を維持する() -> (
    None
):
    """旧指紋の重複hashが一致しても別患者対応の受信を成功扱いしない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-LEGACY-DUPLICATE-OTHER-PATIENT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    other_patient_id = PatientId.generate()
    other_patient_number = await fixture.patient_repo.allocate_patient_number(
        corporate_id=fixture.corporate_id
    )
    await fixture.patient_repo.save(
        replace(patient, id=other_patient_id, patient_number=other_patient_number)
    )
    original_link = next(iter(fixture.patient_external_id_repo.items.values()))
    alternate_link = PatientExternalIdentifier.create(
        corporate_id=fixture.corporate_id,
        store_id=original_link.store_id,
        patient_id=other_patient_id,
        system_name=original_link.system_name,
        external_patient_id=ExternalPatientId("P-LEGACY-OTHER-PATIENT"),
    )
    await fixture.patient_external_id_repo.save(alternate_link)
    changed = replace(
        legitimate,
        patient=replace(
            legitimate.patient,
            external_patient_id=alternate_link.external_patient_id.value,
        ),
    )
    # 重複判定へ到達できる旧保存状態を構築する。期待結果はhashから導出しない。
    incoming_fields = fixture.use_case._fingerprint_bundle(changed)
    incoming_hash = fixture.use_case._combined_fingerprint(incoming_fields)
    legacy_reception = replace(
        reception,
        field_fingerprints=tuple(
            (path, fingerprint)
            for path, fingerprint in reception.field_fingerprints
            if path.value != "patient.external_patient_id"
        ),
        latest_fingerprint=incoming_hash,
    )
    await fixture.reception_repo.save(legacy_reception)
    stored = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert stored is not None
    assert stored.field_fingerprints
    assert all(
        path.value != "patient.external_patient_id"
        for path, _ in stored.field_fingerprints
    )
    assert stored.latest_fingerprint == incoming_hash
    assert stored.patient_id != alternate_link.patient_id
    active_link = await fixture.patient_external_id_repo.get_active_by_source(
        corporate_id=fixture.corporate_id,
        store_id=alternate_link.store_id,
        system_name=alternate_link.system_name,
        external_patient_id=alternate_link.external_patient_id,
    )
    assert active_link is not None
    assert active_link.patient_id == other_patient_id
    before = _snapshot_saved_state(fixture)

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_取込_外部患者ID不一致で薬品なし_拒否し保存状態を維持する() -> None:
    """Rpがない入力も患者同一性を確認し、正常終了で受理しない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-NO-MEDICINES-IDENTITY-CONFLICT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate,
        patient=replace(legitimate.patient, external_patient_id="P-NO-MEDICINES-OTHER"),
        prescription=replace(legitimate.prescription, rps=()),
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_取込_外部患者ID不一致の削除通知_拒否し薬歴と保存状態を維持する() -> None:
    """別患者IDの削除通知で取消・保留・薬歴破棄を実行しない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-DELETE-IDENTITY-CONFLICT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate,
        patient=replace(legitimate.patient, external_patient_id="P-DELETE-OTHER"),
        correction_kind=ExternalCorrectionKind.DELETE,
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
async def test_TC33_TC34_削除通知は実績を保って保留し同じ通知の再送で増えない() -> None:
    """正規化済みD通知で取消可能な実作業を止め、削除監査を冪等に記録する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-DELETE-CORRECTION"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(history)
    assert initial.prescription_id is not None
    assert initial.dispensing_id is not None
    prescription_id = PrescriptionId.parse(initial.prescription_id)
    dispensing_id = DispensingId.parse(initial.dispensing_id)

    deletion_bundle = replace(
        original_bundle, correction_kind=ExternalCorrectionKind.DELETE
    )
    deletion_command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(reception_id.value),
        structured_bundle=deletion_bundle,
    )
    first = await execute_structured_test_command(fixture, deletion_command)

    saved_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id, prescription_id=prescription_id
    )
    saved_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    saved_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert saved_prescription is not None
    assert saved_prescription.status.value == "cancelled"
    assert saved_dispensing is not None
    assert saved_dispensing.status.value == "cancelled"
    assert saved_history is not None
    assert saved_history.soap == history.soap
    assert saved_history.finalized_at == history.finalized_at
    assert len(saved_history.external_corrections) == 1
    assert saved_history.external_corrections[0].kind is ExternalCorrectionKind.DELETE
    assert saved_history.has_pending_correction_review is True
    assert first.has_pending_correction_review is True

    resent = await execute_structured_test_command(fixture, deletion_command)
    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert resent.is_duplicate is True
    assert reloaded_history is not None
    assert reloaded_history.external_corrections == saved_history.external_corrections


@pytest.mark.asyncio
async def test_TC14_完了済み処方と調剤は削除通知後も終端状態を保つ() -> None:
    """完了した処方・調剤は削除通知で取消さず、薬歴に訂正を記録する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-DELETE-TERMINAL-STATE"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(history)
    assert initial.prescription_id is not None
    assert initial.dispensing_id is not None
    prescription_id = PrescriptionId.parse(initial.prescription_id)
    dispensing_id = DispensingId.parse(initial.dispensing_id)
    prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id, prescription_id=prescription_id
    )
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    assert prescription is not None
    assert prescription.status is PrescriptionStatus.READY_FOR_DISPENSING
    assert dispensing is not None

    await fixture.prescription_repo.save(prescription.complete_dispensing())
    await fixture.dispensing_repo.save(complete_dispensing(dispensing))

    result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=replace(
                original_bundle, correction_kind=ExternalCorrectionKind.DELETE
            ),
        ),
    )

    saved_prescription = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id, prescription_id=prescription_id
    )
    saved_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    saved_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert saved_prescription is not None
    assert saved_prescription.status is PrescriptionStatus.DISPENSED
    assert saved_dispensing is not None
    assert saved_dispensing.status is DispensingProcessStatus.COMPLETED
    assert saved_history is not None
    assert saved_history.soap == history.soap
    assert saved_history.finalized_at == history.finalized_at
    assert len(saved_history.external_corrections) == 1
    assert saved_history.external_corrections[0].kind is ExternalCorrectionKind.DELETE
    assert saved_history.has_pending_correction_review is True
    assert result.has_pending_correction_review is True


@pytest.mark.asyncio
async def test_TC10_指導も調剤実績もない下書きは削除通知時に破棄する() -> None:
    """未指導かつ未完了の下書きを削除し、Receptionの参照も外す。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-DELETE-EMPTY-DRAFT"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    draft = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    draft = replace(draft, counselor_id=None, counseled_at=None)
    await fixture.medication_history_repo.save(draft)
    delete_command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        dispenser_staff_id=str(fixture.pharmacist_id.value),
        reception_id=str(reception_id.value),
        structured_bundle=replace(
            original_bundle, correction_kind=ExternalCorrectionKind.DELETE
        ),
    )

    result = await execute_structured_test_command(fixture, delete_command)

    assert (
        await fixture.medication_history_repo.get(
            corporate_id=fixture.corporate_id, record_id=draft.id
        )
        is None
    )
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.medication_history_id is None
    assert result.has_pending_correction_review is False


@pytest.mark.asyncio
async def test_TC11_指導日時がある下書きは削除通知でも保持する() -> None:
    """指導者と指導日時の記録がある下書きは保留訂正として残す。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-DELETE-COUNSELED-DRAFT"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    draft = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )

    result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=replace(
                bundle, correction_kind=ExternalCorrectionKind.DELETE
            ),
        ),
    )

    saved = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=draft.id
    )
    assert saved is not None
    assert len(saved.external_corrections) == 1
    assert result.has_pending_correction_review is True


@pytest.mark.asyncio
async def test_TC12_交付済み調剤に関連する下書きは削除通知でも保持する() -> None:
    """薬剤交付の実績がある薬歴は未確定でも削除対象にしない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-DELETE-COMPLETED-DRAFT"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    draft = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    assert initial.dispensing_id is not None
    dispensing_id = DispensingId.parse(initial.dispensing_id)
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id, dispensing_id=dispensing_id
    )
    assert dispensing is not None
    await fixture.dispensing_repo.save(complete_dispensing(dispensing))

    result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=replace(
                bundle, correction_kind=ExternalCorrectionKind.DELETE
            ),
        ),
    )

    saved = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=draft.id
    )
    assert saved is not None
    assert len(saved.external_corrections) == 1
    assert result.has_pending_correction_review is True


@pytest.mark.asyncio
async def test_TC32_同じ訂正を異なる受付IDで再送しても処方を重ねない() -> None:
    """外部内容のハッシュ値が同じなら受付IDが異なっても既存訂正を再利用する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-NEW-RECEPTION-RESEND"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(history)
    correction_bundle = replace(
        original_bundle,
        prescription=replace(original_bundle.prescription, doctor_name="変更後の医師"),
        correction_kind=ExternalCorrectionKind.UPDATE,
    )
    first_correction = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=correction_bundle,
        ),
    )
    assert first_correction.has_pending_correction_review is True
    prescription_count = len(fixture.prescription_repo.items)
    second_reception_id = ReceptionId.generate()

    resent = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(second_reception_id.value),
            structured_bundle=correction_bundle,
        ),
    )

    saved_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert resent.is_duplicate is True
    assert len(fixture.prescription_repo.items) == prescription_count
    assert saved_history is not None
    assert len(saved_history.external_corrections) == 1


@pytest.mark.asyncio
async def test_TC31_解決済みの外部訂正を再送しても保留へ戻さない() -> None:
    """U/B訂正を解決した後に同一通知が再送されても、解決済み状態を維持し保留に戻さない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC31-RESOLVED-RESEND"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    history = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(history)

    # 訂正を受信
    correction_bundle = replace(
        original_bundle,
        prescription=replace(original_bundle.prescription, doctor_name="変更後の医師"),
        correction_kind=ExternalCorrectionKind.UPDATE,
    )
    first_correction = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=correction_bundle,
        ),
    )
    assert first_correction.has_pending_correction_review is True

    # 薬剤師が外部訂正を解決（NO_ACTION）
    saved_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert saved_history is not None
    resolved_history = saved_history.review_external_correction(
        correction_id=saved_history.external_corrections[0].correction_id,
        decision=ExternalCorrectionDecision.NO_ACTION,
        reason="内容を確認し、薬歴への反映は不要と判断した。",
        reviewed_by=fixture.pharmacist_id,
        reviewed_at=ExternalCorrectionTimestamp(fixture.clock.now()),
    )
    await fixture.medication_history_repo.save(resolved_history)
    assert resolved_history.has_pending_correction_review is False
    assert (
        resolved_history.external_corrections[0].status
        is ExternalCorrectionStatus.RESOLVED
    )

    # 同一通知を同一受付IDで再送
    resent_same_reception = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=correction_bundle,
        ),
    )
    assert resent_same_reception.has_pending_correction_review is False

    # 別受付IDで再送
    second_reception_id = ReceptionId.generate()
    resent_new_reception = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(second_reception_id.value),
            structured_bundle=correction_bundle,
        ),
    )
    assert resent_new_reception.has_pending_correction_review is False

    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=history.id
    )
    assert reloaded_history is not None
    assert len(reloaded_history.external_corrections) == 1
    assert (
        reloaded_history.external_corrections[0].status
        is ExternalCorrectionStatus.RESOLVED
    )
    assert len(reloaded_history.external_corrections[0].review_events) == 1


@pytest.mark.asyncio
async def test_TC35_削除保留を再登録処方と照合して解決する() -> None:
    """D-fileの削除保留を再登録処方との照合判断で解決する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC35-DELETE-RESOLVE"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    finalized = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(finalized)

    # D-file削除通知を受信
    delete_result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=replace(
                bundle, correction_kind=ExternalCorrectionKind.DELETE
            ),
        ),
    )
    assert delete_result.has_pending_correction_review is True

    # 薬歴に削除訂正が保留として記録されていることを確認
    pending_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=finalized.id
    )
    assert pending_history is not None
    assert pending_history.external_corrections[0].kind is ExternalCorrectionKind.DELETE
    assert (
        pending_history.external_corrections[0].status
        is ExternalCorrectionStatus.PENDING
    )

    # 再登録された処方箋を準備
    reregistered_rx = create_prescription(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=finalized.patient_id,
    )
    await fixture.prescription_repo.save(reregistered_rx)

    # 照合判断（MATCH_REREGISTERED_PRESCRIPTION）で解決
    resolved = pending_history.review_external_correction(
        correction_id=pending_history.external_corrections[0].correction_id,
        decision=ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION,
        reason="再登録処方箋との一致を確認し解決した。",
        reviewed_by=fixture.pharmacist_id,
        reviewed_at=ExternalCorrectionTimestamp(fixture.clock.now()),
        matched_prescription_id=reregistered_rx.id,
    )
    await fixture.medication_history_repo.save(resolved)

    # 検証: 削除元の薬歴・原本SOAPは完全に保護され、照合先処方IDが監査記録される
    assert resolved.soap == finalized.soap
    assert resolved.has_pending_correction_review is False
    assert resolved.external_corrections[0].status is ExternalCorrectionStatus.RESOLVED
    review_event = resolved.external_corrections[0].review_events[-1]
    assert (
        review_event.decision
        is ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
    )
    assert review_event.matched_prescription_id == reregistered_rx.id


@pytest.mark.asyncio
async def test_TC35_削除保留を薬歴追記訂正で解決する() -> None:
    """削除保留の薬歴へ追記訂正を追加し、削除事実と原本を保持して解決する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-TC35-DELETE-AMEND"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    history = await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    finalized = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(
        counselor_id=fixture.pharmacist_id,
        counseled_at=CounselingTimestamp(fixture.clock.now()),
        finalized_at=FinalizedTimestamp(fixture.clock.now()),
        finalized_by=fixture.pharmacist_id,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )
    await fixture.medication_history_repo.save(finalized)

    deletion_result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            dispenser_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=replace(
                bundle, correction_kind=ExternalCorrectionKind.DELETE
            ),
        ),
    )
    assert deletion_result.has_pending_correction_review is True

    pending = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id, record_id=finalized.id
    )
    assert pending is not None
    correction = pending.external_corrections[0]
    assert correction.kind is ExternalCorrectionKind.DELETE
    assert correction.status is ExternalCorrectionStatus.PENDING

    amended = pending.review_external_correction(
        correction_id=correction.correction_id,
        decision=ExternalCorrectionDecision.AMEND,
        reason="削除された処方内容を確認し、患者への説明を追記した。",
        reviewed_by=fixture.pharmacist_id,
        reviewed_at=ExternalCorrectionTimestamp(fixture.clock.now()),
        amended_soap=create_soap(subjective="削除された処方内容の説明を追記。"),
    )
    await fixture.medication_history_repo.save(amended)

    assert amended.soap == finalized.soap
    assert amended.has_pending_correction_review is False
    assert amended.external_corrections[0].status is ExternalCorrectionStatus.RESOLVED
    assert len(amended.amendments) == 1
    assert amended.amendments[0].amended_soap.subjective[0].text.value == (
        "削除された処方内容の説明を追記。"
    )
    event = amended.external_corrections[0].review_events[-1]
    assert event.decision is ExternalCorrectionDecision.AMEND
    assert event.amendment_id == amended.amendments[0].amendment_id


@pytest.mark.asyncio
async def test_取込_患者ID指紋欠損で有効リンク一致_正当属性訂正と参照を維持する() -> (
    None
):
    """旧指紋でも受付患者への有効な対応があれば正当な属性訂正を受理する。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-LEGACY-VALID-PATIENT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    legacy = replace(
        reception,
        field_fingerprints=tuple(
            (path, fingerprint)
            for path, fingerprint in reception.field_fingerprints
            if path.value != "patient.external_patient_id"
        ),
    )
    await fixture.reception_repo.save(legacy)
    link = await fixture.patient_external_id_repo.get_active_by_source(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        system_name=ExternalSystemName("recept"),
        external_patient_id=ExternalPatientId(legitimate.patient.external_patient_id),
    )
    assert link is not None
    assert link.patient_id == legacy.patient_id
    assert all(
        path.value != "patient.external_patient_id"
        for path, _ in legacy.field_fingerprints
    )
    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate, patient=replace(legitimate.patient, kanji_name="正当 訂正")
    )

    # Act
    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, changed)
    )

    # Assert
    assert not result.is_duplicate
    assert result.patient_id == initial.patient_id
    assert result.prescription_id == initial.prescription_id
    assert result.dispensing_id == initial.dispensing_id
    assert reception.medication_history_id is not None
    assert result.medication_history_id == str(reception.medication_history_id.value)
    updated = fixture.patient_repo.items[patient_id]
    assert updated.names.kanji.full_name == "正当 訂正"
    assert len(updated.profile_history) == len(patient.profile_history) + 1
    assert updated.profile_history[:-1] == patient.profile_history
    assert "patient.kanji_name" in updated.profile_history[-1].changed_fields
    assert updated.profile_history[-1].external_patient_id == link.external_patient_id
    assert updated.heading_history == patient.heading_history
    after = _snapshot_saved_state(fixture)
    assert after[1] == before[1]
    for index in (3, 4):
        assert after[index] == before[index]
    assert after[5].keys() == before[5].keys()
    for record_id, saved_record in before[5].items():
        for field in (
            "patient_id",
            "prescription_id",
            "dispensing_id",
            "soap",
        ):
            assert after[5][record_id][field] == saved_record[field]
    current_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert current_reception is not None
    assert current_reception.patient_id == reception.patient_id
    assert current_reception.prescription_id == reception.prescription_id
    assert current_reception.dispensing_id == reception.dispensing_id
    assert current_reception.medication_history_id == reception.medication_history_id
    assert current_reception.correction_history[:-1] == reception.correction_history
    assert (
        len(current_reception.correction_history)
        == len(reception.correction_history) + 1
    )
    assert current_reception.source_data_history[:-1] == reception.source_data_history


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inactive_only", (False, True), ids=("対応なし", "無効対応のみ")
)
async def test_取込_患者ID指紋欠損で有効対応なし_拒否し新リンクを作らない(
    inactive_only: bool,
) -> None:
    """旧指紋で照合不能な受信からリンクを作って同一性確認済みと扱わない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-LEGACY-NO-ACTIVE-LINK"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    legacy = replace(
        reception,
        field_fingerprints=tuple(
            (path, fingerprint)
            for path, fingerprint in reception.field_fingerprints
            if path.value != "patient.external_patient_id"
        ),
    )
    await fixture.reception_repo.save(legacy)
    incoming_id = ExternalPatientId("P-LEGACY-NO-ACTIVE-LINK")
    if inactive_only:
        inactive_link = PatientExternalIdentifier.create(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=patient_id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=incoming_id,
        ).deactivate()
        await fixture.patient_external_id_repo.save(inactive_link)
    assert (
        await fixture.patient_external_id_repo.get_active_by_source(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=incoming_id,
        )
        is None
    )
    matching_links = [
        item
        for item in fixture.patient_external_id_repo.items.values()
        if item.external_patient_id == incoming_id
    ]
    assert len(matching_links) == int(inactive_only)
    assert all(not item.is_active for item in matching_links)
    before = _snapshot_saved_state(fixture)
    link_count = len(fixture.patient_external_id_repo.items)
    changed = replace(
        legitimate,
        patient=replace(legitimate.patient, external_patient_id=incoming_id.value),
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before
    assert len(fixture.patient_external_id_repo.items) == link_count


@pytest.mark.asyncio
async def test_取込_患者ID指紋欠損で別患者の属性訂正_拒否し両患者の保存状態を維持する() -> (
    None
):
    """重複でない属性訂正でも別患者のリンクを受付患者へ適用しない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-LEGACY-CORRECTION-OTHER-PATIENT"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    other_patient_id = PatientId.generate()
    other_patient_number = await fixture.patient_repo.allocate_patient_number(
        corporate_id=fixture.corporate_id
    )
    await fixture.patient_repo.save(
        replace(patient, id=other_patient_id, patient_number=other_patient_number)
    )
    original_link = next(iter(fixture.patient_external_id_repo.items.values()))
    alternate_link = PatientExternalIdentifier.create(
        corporate_id=fixture.corporate_id,
        store_id=original_link.store_id,
        patient_id=other_patient_id,
        system_name=original_link.system_name,
        external_patient_id=ExternalPatientId("P-LEGACY-CORRECTION-OTHER"),
    )
    await fixture.patient_external_id_repo.save(alternate_link)
    changed = replace(
        legitimate,
        patient=replace(
            legitimate.patient,
            external_patient_id=alternate_link.external_patient_id.value,
            kanji_name="別人 訂正",
        ),
    )
    # 旧指紋欠損を再現し、今回は重複hashが一致しない属性訂正と明示確認する。
    incoming_fields = fixture.use_case._fingerprint_bundle(changed)
    incoming_hash = fixture.use_case._combined_fingerprint(incoming_fields)
    legacy_reception = replace(
        reception,
        field_fingerprints=tuple(
            (path, fingerprint)
            for path, fingerprint in reception.field_fingerprints
            if path.value != "patient.external_patient_id"
        ),
    )
    await fixture.reception_repo.save(legacy_reception)
    stored = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert stored is not None
    assert stored.field_fingerprints
    assert all(
        path.value != "patient.external_patient_id"
        for path, _ in stored.field_fingerprints
    )
    assert stored.latest_fingerprint != incoming_hash
    assert stored.patient_id != alternate_link.patient_id
    active_link = await fixture.patient_external_id_repo.get_active_by_source(
        corporate_id=fixture.corporate_id,
        store_id=alternate_link.store_id,
        system_name=alternate_link.system_name,
        external_patient_id=alternate_link.external_patient_id,
    )
    assert active_link is not None
    assert active_link.patient_id == other_patient_id
    before = _snapshot_saved_state(fixture)

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "different_scope",
    ("corporate", "store", "source"),
    ids=("別法人", "別店舗", "別受信元"),
)
async def test_取込_患者ID指紋欠損で他スコープのリンクのみ_拒否し患者情報を露出しない(
    different_scope: str,
) -> None:
    """文字列一致でも他法人・他店舗・他受信元のリンクを同一性確認に使わない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-LEGACY-FOREIGN-SCOPE"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    await fixture.reception_repo.save(
        replace(
            reception,
            field_fingerprints=tuple(
                (path, fingerprint)
                for path, fingerprint in reception.field_fingerprints
                if path.value != "patient.external_patient_id"
            ),
        )
    )
    foreign_corporate = (
        CorporateId.generate()
        if different_scope == "corporate"
        else fixture.corporate_id
    )
    foreign_store_id = fixture.store_id
    if different_scope in ("corporate", "store"):
        foreign_store = create_store(
            corporate_id=foreign_corporate, name="別スコープ薬局"
        )
        await fixture.store_repo.save(foreign_store)
        foreign_store_id = foreign_store.id
    foreign_patient = replace(
        patient,
        id=PatientId.generate(),
        corporate_id=foreign_corporate,
        patient_number=await fixture.patient_repo.allocate_patient_number(
            foreign_corporate
        ),
        names=PersonNames.create(
            last_name="非公開",
            first_name="患者",
            last_name_kana="ヒコウカイ",
            first_name_kana="カンジャ",
        ),
    )
    await fixture.patient_repo.save(foreign_patient)
    incoming_id = ExternalPatientId("P-FOREIGN-SCOPE-ONLY")
    foreign_link = PatientExternalIdentifier.create(
        corporate_id=foreign_corporate,
        store_id=foreign_store_id,
        patient_id=foreign_patient.id,
        system_name=ExternalSystemName(
            "other-source" if different_scope == "source" else "recept"
        ),
        external_patient_id=incoming_id,
    )
    await fixture.patient_external_id_repo.save(foreign_link)
    assert (
        await fixture.patient_external_id_repo.get_active_by_source(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=incoming_id,
        )
        is None
    )
    before = _snapshot_saved_state(fixture)
    changed = replace(
        legitimate,
        patient=replace(legitimate.patient, external_patient_id=incoming_id.value),
    )

    # Act
    with pytest.raises(NsipsPatientIdentityConflictError) as caught:
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, changed)
        )

    # Assert
    assert _snapshot_saved_state(fixture) == before
    message = str(caught.value)
    for private_value in (
        "非公開 患者",
        "元患者の継続申し送り",
        str(foreign_patient.id.value),
        str(foreign_corporate.value),
        str(foreign_store_id.value),
        incoming_id.value,
    ):
        assert private_value not in message


@pytest.mark.asyncio
async def test_取込_不一致拒否後に元IDへ戻す_属性訂正と再送冪等性を維持する() -> None:
    """拒否内容のIDを照合済み元IDに戻した訂正は成功し、同内容再送は履歴を増やさない。"""
    # Arrange
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-IDENTITY-RECOVERY"
    )
    initial = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, original)
    )
    await _save_history_after_pharmacist_writing(
        fixture, reception_id=reception_id, ingest_result=initial
    )
    legitimate = replace(
        original, patient=replace(original.patient, address="東京都品川区三丁目")
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, legitimate)
    )
    patient_id = PatientId.parse(initial.patient_id)
    patient = fixture.patient_repo.items[patient_id]
    patient = patient.change_heading(
        PatientHeadingContent(
            summary=PatientHeadingText("元患者の継続申し送り"), notes=None
        ),
        expected_revision=0,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=fixture.clock.now(),
    )
    await fixture.patient_repo.save(patient)
    assert patient.profile_history
    assert patient.heading_history
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.correction_history
    assert reception.source_data_history
    assert fixture.patient_external_id_repo.items
    assert fixture.prescription_repo.items
    assert fixture.dispensing_repo.items
    assert fixture.medication_history_repo.items

    before = _snapshot_saved_state(fixture)
    conflicting = replace(
        legitimate,
        patient=replace(
            legitimate.patient,
            external_patient_id="P-OTHER-PERSON",
            kanji_name="別人 花子",
            kana_name="ベツジン ハナコ",
            birth_date=date(1980, 1, 2),
            gender="1",
            postal_code="1000002",
            address="東京都港区二丁目",
            phone_number="03-1111-2222",
        ),
    )

    # Act: 拒否後、外部IDだけ元の値へ戻した内容を送る。
    with pytest.raises(NsipsPatientIdentityConflictError):
        await execute_structured_test_command(
            fixture, _command_for_reception(fixture, reception_id, conflicting)
        )
    assert _snapshot_saved_state(fixture) == before
    restored = replace(
        conflicting,
        patient=replace(
            conflicting.patient,
            external_patient_id=legitimate.patient.external_patient_id,
        ),
    )
    result = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, restored)
    )

    # Assert
    assert not result.is_duplicate
    assert result.patient_id == initial.patient_id
    assert result.prescription_id == initial.prescription_id
    assert result.dispensing_id == initial.dispensing_id
    assert reception.medication_history_id is not None
    assert result.medication_history_id == str(reception.medication_history_id.value)
    updated = fixture.patient_repo.items[patient_id]
    assert updated.names.kanji.full_name == "別人 花子"
    assert updated.names.kana.full_name == "ベツジン ハナコ"
    assert updated.birth_date is not None
    assert updated.birth_date.value == date(1980, 1, 2)
    assert updated.address is not None
    assert updated.address.value == "東京都港区二丁目"
    assert len(updated.profile_history) == len(patient.profile_history) + 1
    assert updated.profile_history[:-1] == patient.profile_history
    assert updated.heading_history == patient.heading_history
    successful_state = _snapshot_saved_state(fixture)
    for index in (2, 3, 4, 5):
        assert successful_state[index].keys() == before[index].keys()
        for identifier, saved in before[index].items():
            for field in (
                "patient_id",
                "prescription_id",
                "dispensing_id",
                "medication_history_id",
            ):
                if field in saved:
                    assert successful_state[index][identifier][field] == saved[field]

    # Act: 成功内容をもう一度送る。
    duplicate = await execute_structured_test_command(
        fixture, _command_for_reception(fixture, reception_id, restored)
    )

    # Assert
    assert duplicate.is_duplicate
    assert duplicate.patient_id == result.patient_id
    assert duplicate.prescription_id == result.prescription_id
    assert duplicate.dispensing_id == result.dispensing_id
    assert duplicate.medication_history_id == result.medication_history_id
    assert _snapshot_saved_state(fixture) == successful_state
