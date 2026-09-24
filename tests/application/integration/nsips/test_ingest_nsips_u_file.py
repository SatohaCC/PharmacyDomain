"""NSIPS Uファイル（処方訂正）取込時の真正性管理テスト。"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
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
from app.domain.medication_history.primitives import (
    CounselingMethod,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.value_objects import (
    HandbookStatus,
    ResidualDrugRecord,
)
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
)
from app.domain.prescription.primitives import PrescriptionDocumentNumber
from app.domain.reception.primitives import ReceptionId
from tests.application.integration.nsips.helpers import (
    NsipsFixture,
    create_fixture,
    execute_structured_test_command,
)


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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
        operator_staff_id=str(fixture.pharmacist_id.value),
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
    assert result.medication_history_id is not None
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
    """同一受付の再送は永続化された指紋で冪等になる。"""
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
    """Bundleの業務フィールドを一つずつ変え、再送重複で捨てない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC57-ALL-FIELDS",
    )
    changed = _replace_bundle_path(original, path, changed_value)
    assert isinstance(changed, NsipsBundle)

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
    assert (
        profile_change.external_patient_id.value == original.patient.external_patient_id
    )
    assert profile_change.recorded_at == fixture.clock.now()
    assert profile_change.received_profile.address is not None
    assert profile_change.received_profile.address.value == changed.patient.address
    assert (
        profile_change.received_profile.birth_date.value == changed.patient.birth_date
    )
    assert patient.names.kanji.full_name == original.patient.kanji_name


@pytest.mark.asyncio
async def test_tc67_同じ受付の患者訂正再送は一件で別受付は別履歴になる() -> None:
    """同一受付の訂正再送は重ねず、別受付で同じ受信値なら追記する。"""
    fixture = await create_fixture()
    first_reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(document_number="DOC-TC67-SAME")
    corrected = replace(
        original,
        patient=replace(original.patient, address="東京都新宿区一丁目"),
    )
    await execute_structured_test_command(
        fixture, _command_for_reception(fixture, first_reception_id, original)
    )
    corrected_command = _command_for_reception(
        fixture,
        first_reception_id,
        corrected,
    )

    await execute_structured_test_command(fixture, corrected_command)
    await execute_structured_test_command(fixture, corrected_command)
    second_reception_id = ReceptionId.generate()
    second_reception = replace(
        corrected,
        prescription=replace(
            corrected.prescription,
            document_number="DOC-TC67-OTHER-RECEPTION",
        ),
    )
    await execute_structured_test_command(
        fixture,
        _command_for_reception(
            fixture,
            second_reception_id,
            second_reception,
        ),
    )

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
    assert len(patient.profile_history) == 2
    assert [item.reception_id for item in patient.profile_history] == [
        first_reception_id,
        second_reception_id,
    ]


@pytest.mark.asyncio
async def test_tc68_外部患者ID訂正は受付患者と既存リンクを維持する() -> None:
    """外部患者IDだけ変わったU相当訂正で既存Patientリンクを変更しない。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC68-EXTERNAL-ID",
    )
    await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, reception_id, original),
    )
    original_patient_id = next(iter(fixture.patient_repo.items.values())).id
    original_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=original_patient_id,
    )
    changed = replace(
        original,
        patient=replace(original.patient, external_patient_id="P-TC68-CHANGED"),
    )

    result = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, reception_id, changed),
    )

    assert result.patient_id == str(original_patient_id.value)
    assert len(fixture.patient_repo.items) == 1
    current_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=original_patient_id,
    )
    assert current_links == original_links
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=original_patient_id,
    )
    assert patient is not None
    assert len(patient.profile_history) == 1
    assert "patient.external_patient_id" in patient.profile_history[0].changed_fields
    assert (
        patient.profile_history[0].received_profile.names.kanji.full_name
        == original.patient.kanji_name
    )


@pytest.mark.asyncio
async def test_tc69_患者プロフィール受信Noneで既存値や履歴を消さない() -> None:
    """患者情報の受信欠損をマスターからの削除指示として扱わない。"""
    fixture = await create_fixture()
    original = _bundle_with_all_business_sections(
        document_number="DOC-TC69-NONE-INITIAL",
    )
    first = await execute_structured_test_command(
        fixture,
        _command_for_reception(fixture, ReceptionId.generate(), original),
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
        fixture,
        _command_for_reception(fixture, ReceptionId.generate(), received_none),
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
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC46-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
            reception_id=str(reception_id.value),
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
    reception_id = ReceptionId.generate()
    original_bundle = _structured_bundle_for_non_prescription_correction(
        document_number=f"TC47-{field_name}"
    )
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=original,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=initial_bundle,
        ),
    )
    corrected = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
            operator_staff_id=str(fixture.pharmacist_id.value),
            reception_id=str(reception_id.value),
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
