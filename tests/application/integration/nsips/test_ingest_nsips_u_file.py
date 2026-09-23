"""NSIPS Uファイル（処方訂正）取込時の真正性管理テスト。"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
)
from app.application.integration.nsips.models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)
from app.domain.medication_history import (
    CounselingMethod,
    HandbookStatus,
    MedicationHistoryRecordId,
    ResidualDrugRecord,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionDocumentNumber
from tests.application.integration.nsips.helpers import (
    create_fixture,
    execute_structured_test_command,
)


@pytest.mark.asyncio
async def test_ingest_u_file_with_finalized_history_records_correction() -> None:
    """確定済み薬歴が存在する処方箋のUファイルを訂正証跡として保管する。"""
    fixture = await create_fixture()

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
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_initial,
        ),
    )
    assert res_initial.medication_history_id is not None
    history_id = MedicationHistoryRecordId.parse(res_initial.medication_history_id)

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
    ).finalize(finalized_by=fixture.pharmacist_id)
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
            operator_staff_id=str(fixture.pharmacist_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_initial,
        ),
    )
    history_id = MedicationHistoryRecordId.parse(
        res_initial.medication_history_id  # type: ignore[arg-type]
    )

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
            operator_staff_id=str(fixture.pharmacist_id.value),
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
async def test_tc46_患者の識別属性差分は要確認として記録し既存値を維持する(
    field_name: str,
) -> None:
    """患者識別・属性差分を重複扱いせず、既存患者と対応付けを保持する。"""
    fixture = await create_fixture()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC46-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=original_bundle,
        ),
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

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=_bundle_with_patient_difference(
                original_bundle, field_name
            ),
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.has_pending_correction_review is True
    history_id = MedicationHistoryRecordId.parse(corrected.medication_history_id or "")
    corrected_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert corrected_history is not None
    assert len(corrected_history.external_corrections) == 1
    correction = corrected_history.external_corrections[0]
    assert field_name in (correction.details or "")

    unchanged_patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert unchanged_patient is not None
    assert unchanged_patient.names == original_patient.names
    assert unchanged_patient.birth_date == original_patient.birth_date
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
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC47-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=original_bundle,
        ),
    )
    history_id = MedicationHistoryRecordId.parse(initial.medication_history_id or "")
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
    ).finalize(finalized_by=fixture.pharmacist_id)
    await fixture.medication_history_repo.save(finalized_history)
    original_dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=history.dispensing_id,
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
            operator_staff_id=str(fixture.pharmacist_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=original,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=corrected_bundle,
        ),
    )
    assert corrected.has_pending_correction_review is True
    assert corrected.medication_history_id == initial.medication_history_id
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=MedicationHistoryRecordId.parse(
            corrected.medication_history_id or ""
        ),
    )
    assert history is not None
    assert history.external_corrections[-1].corrected_at.value == fixture.clock.now()


@pytest.mark.asyncio
async def test_tc33_加算だけが変わった訂正を単純再送として捨てない() -> None:
    """処方薬が同じでも加算差分は重複応答で消さない。"""
    fixture = await create_fixture()
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=corrected_bundle,
        ),
    )

    assert corrected.is_duplicate is False
    assert corrected.prescription_id == initial.prescription_id


@pytest.mark.asyncio
async def test_tc34_調剤日だけが変わった訂正を単純再送として捨てない() -> None:
    """同一処方箋番号でも調剤日の差分を重複扱いで隠さない。"""
    fixture = await create_fixture()
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=corrected_bundle,
        ),
    )

    assert corrected.is_duplicate is False


@pytest.mark.asyncio
async def test_tc35_確定薬歴の加算訂正で原本を保持して要確認にする() -> None:
    """確定後の加算差分は原本を書き換えず訂正確認として残す。"""
    fixture = await create_fixture()
    initial_bundle = _structured_bundle_for_non_prescription_correction(
        document_number="DOC-UFILE-FINALIZED-ADDITION",
        additions=(NsipsAdditionInfo(code="140000110", name="加算A", points=100),),
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    assert initial.medication_history_id is not None
    history_id = MedicationHistoryRecordId.parse(initial.medication_history_id)
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    finalized = history.update_draft(
        method=CounselingMethod.FACE_TO_FACE,
        handbook_status=HandbookStatus(presented=True),
        residual_drug=ResidualDrugRecord.none_remaining(),
        information_sheet_provided=False,
    ).finalize(finalized_by=fixture.pharmacist_id)
    await fixture.medication_history_repo.save(finalized)

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
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
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=_structured_bundle_for_non_prescription_correction(
                document_number="DOC-UFILE-DRAFT-ADDITION",
                additions=(
                    NsipsAdditionInfo(code="140000110", name="加算A", points=100),
                ),
            ),
        ),
    )
    assert initial.medication_history_id is not None
    history_id = MedicationHistoryRecordId.parse(initial.medication_history_id)

    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=_structured_bundle_for_non_prescription_correction(
                document_number="DOC-UFILE-DRAFT-ADDITION",
                additions=(
                    NsipsAdditionInfo(code="140000210", name="加算B", points=200),
                ),
            ),
        ),
    )

    assert corrected.is_duplicate is False
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    assert history.is_finalized is False
    if corrected.has_pending_correction_review:
        assert history.billing_additions[0].code.value == "140000110"
    else:
        assert history.billing_additions[0].code.value == "140000210"
