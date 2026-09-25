"""薬歴前提NSIPS受付取込パイプラインの合成Fixture回帰テスト。"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
)
from app.application.integration.nsips.mapper import NsipsDataMapper
from app.application.integration.nsips.models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
)
from app.application.integration.nsips.parser import NsipsParser
from app.application.patient.get_patient import GetPatientQuery, GetPatientUseCase
from app.application.patient.register_patient import RegisterPatientUseCase
from app.application.reception.exceptions import ReceptionCoverageSelectionError
from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.dispensing.exceptions import DispensingOutsidePrescriptionPeriodError
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import CoverageSelectionRecordId
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.integration.nsips.helpers import (
    create_fixture,
    execute_structured_test_command,
)

# ==============================================================================
# 1. 合成入力の構文解析回帰（対象NSIPS版の仕様適合を示さない）
# ==============================================================================


def test_合成レコード03風入力の解析() -> None:
    """合成入力を解析できることだけを確認し、NSIPS版への適合は主張しない。"""
    parser = NsipsParser()
    text = (
        "1,20260920,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
        "3,138001,記号A,番号123,01,1,54130012,1234567\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    bundle = parser.parse(text)
    assert bundle.insurance is not None
    assert bundle.insurance.insurer_number == "138001"
    assert bundle.insurance.insured_symbol == "記号A"
    assert bundle.insurance.insured_number == "番号123"
    assert bundle.insurance.branch_number == "01"
    assert bundle.insurance.insured_type is None
    assert bundle.insurance.public_payer_number_1 == "54130012"
    assert bundle.insurance.public_recipient_number_1 == "1234567"


def test_合成レコード04風入力の解析() -> None:
    """合成入力から指定した調剤日を読む。対象版の列定義を示すテストではない。"""
    parser = NsipsParser()
    text = (
        "1,20260920,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
        "4,20260922,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    bundle = parser.parse(text)
    assert bundle.dispensed_date == date(2026, 9, 22)


def test_合成レコード08風入力の解析() -> None:
    """合成入力の加算行を読み、対象版の列定義を示すテストではない。"""
    parser = NsipsParser()
    text = (
        "1,20260920,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
        "8,140000110,特定薬剤管理指導加算２,1\n"
        "8,140000210,吸入薬指導加算,1\n"
    )
    bundle = parser.parse(text)
    assert len(bundle.additions) == 2
    assert bundle.additions[0].code == "140000110"
    assert bundle.additions[0].name == "特定薬剤管理指導加算２"
    assert bundle.additions[1].code == "140000210"
    assert bundle.additions[1].name == "吸入薬指導加算"


def test_合成入力で調剤日行が省略された場合は未設定のまま() -> None:
    """調剤日行を含まない合成入力は未設定のままになる。"""
    parser = NsipsParser()
    text = (
        "1,20260920,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    bundle = parser.parse(text)
    assert bundle.dispensed_date is None


# ==============================================================================
# 2. 合成入力のデータマッピング回帰
# ==============================================================================


def test_tc09_明示された保険情報を変更せず資格登録Commandへ写す() -> None:
    """給付割合、区分、枝番、番号、公費順位を入力どおり保持する。"""
    mapper = NsipsDataMapper()
    insurance = NsipsInsuranceInfo(
        insurer_number="138001",
        insured_symbol="記号A",
        insured_number="番号123",
        branch_number="01",
        insured_type="self",
        benefit_ratio=80,
        public_payer_number_1="54130012",
        public_recipient_number_1="1234567",
    )
    bundle = NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id="P-1001",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-001",
            issued_date=date(2026, 9, 20),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
        ),
        dispensed_date=date(2026, 9, 22),
        insurance=insurance,
    )

    cov_commands = mapper.to_coverage_commands(
        bundle, corporate_id="corp-1", patient_id="pat-1"
    )
    assert len(cov_commands) == 2
    # 1件目は保険証
    assert cov_commands[0].coverage_type == "insurance"
    assert cov_commands[0].insurer_number == "138001"
    assert cov_commands[0].insured_symbol == "記号A"
    assert cov_commands[0].insured_number == "番号123"
    assert cov_commands[0].branch_number == "01"
    assert cov_commands[0].benefit_ratio == 80
    # 2件目は公費1
    assert cov_commands[1].coverage_type == "public_expense"
    assert cov_commands[1].payer_number == "54130012"
    assert cov_commands[1].recipient_number == "1234567"


def test_処方日と調剤日の独立マッピング() -> None:
    """処方日と調剤日を別々のコマンド項目へ写す。"""
    mapper = NsipsDataMapper()
    bundle = NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id="P-1001",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-001",
            issued_date=date(2026, 9, 20),
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
                    dispensing_quantity=14,
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
        dispensed_date=date(2026, 9, 22),
    )

    presc_cmd = mapper.to_prescription_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        patient_id="pat-1",
        coverage_selection_record_id="cov-rec-1",
    )
    assert presc_cmd.issued_date == date(2026, 9, 20)
    assert presc_cmd.coverage_selection_record_id == "cov-rec-1"

    disp_cmd = mapper.to_dispensing_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        prescription_id="presc-1",
        dispenser_id="disp-1",
    )
    assert disp_cmd.dispensed_date == date(2026, 9, 22)


def test_加算はSOAP臨床記載と分けて薬歴Commandへ写す() -> None:
    """NSIPS加算を構造化して保持し、薬歴未確認項目や保険を捏造しない。"""
    mapper = NsipsDataMapper()
    bundle = NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id="P-1001",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-001",
            issued_date=date(2026, 9, 20),
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
                    dispensing_quantity=14,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="アムロジピン",
                            dosage=Decimal("1"),
                            unit="錠",
                        ),
                    ),
                    preparation_method="PACKAGE_UNIT",
                ),
            ),
        ),
        dispensed_date=date(2026, 9, 22),
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="記号A",
            insured_number="番号123",
        ),
        additions=(
            NsipsAdditionInfo(
                code="140000110",
                name="特定薬剤管理指導加算２",
                points=100,
                quantity=1,
            ),
        ),
    )

    hist_cmd = mapper.to_medication_history_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        dispensing_id="disp-1",
    )
    assert hist_cmd.billing_additions is not None
    assert len(hist_cmd.billing_additions) == 1
    assert hist_cmd.billing_additions[0].code == "140000110"
    assert hist_cmd.billing_additions[0].name == "特定薬剤管理指導加算２"

    # SOAP Objective は処方・調剤の観察可能な事実だけを含める。
    obj_text = "\n".join(note.text for note in hist_cmd.soap.objective)
    assert "特定薬剤管理指導加算２" not in obj_text
    assert "保険情報:" not in obj_text
    assert "アムロジピン" in obj_text
    assert "一包化" in obj_text or "PACKAGE_UNIT" in obj_text
    assert hist_cmd.method is None
    assert hist_cmd.handbook_status is None
    assert hist_cmd.residual_drug is None
    assert hist_cmd.information_sheet_provided is None
    assert getattr(hist_cmd, "source_system", None) == "NSIPS"
    assert getattr(hist_cmd.billing_additions[0], "points", None) == 100
    assert getattr(hist_cmd.billing_additions[0], "quantity", None) == 1


# ==============================================================================
# 3. Fake Repositoryを用いた受付取込回帰
# ==============================================================================


@pytest.mark.asyncio
async def test_tc12_合成入力による受付取込は取込時刻だけを薬歴へ記録する() -> None:
    """合成Fixtureの既存経路を確認する。NSIPS版の適合を示すケースではない。"""
    fixture = await create_fixture()
    text = (
        "1,20260920,DOC-FULL-01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-2001,ヤマダタロウ,山田太郎,1,19800101\n"
        "3,138001,記号A,番号123,01,1,54130012,1234567\n"
        "4,20260922,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
        "8,140000110,特定薬剤管理指導加算２,1\n"
    )
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text=text,
    )

    result = await execute_structured_test_command(fixture, cmd)

    # 1. 結果DTOの検証
    assert result.prescription_id is not None
    assert result.dispensing_id is not None
    assert result.medication_history_id is not None
    assert result.coverage_selection_record_id is not None
    assert result.dispensed_date == "2026-09-22"
    assert "特定薬剤管理指導加算２" in result.addition_names

    # 2. 保険資格および選択履歴の検証
    presc = await fixture.prescription_repo.get(
        corporate_id=fixture.corporate_id,
        prescription_id=PrescriptionId.parse(result.prescription_id),
    )
    assert presc is not None
    assert presc.coverage_selection_record_id is not None
    assert (
        str(presc.coverage_selection_record_id.value)
        == result.coverage_selection_record_id
    )

    # 3. 調剤日（使用期間内 9/20〜9/23）の検証
    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=DispensingId.parse(result.dispensing_id),
    )
    assert dispensing is not None
    assert dispensing.dispensed_date.value == date(2026, 9, 22)

    # 4. 薬歴集約に加算が記録されていることの検証
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=MedicationHistoryRecordId.parse(result.medication_history_id),
    )
    assert history is not None
    assert len(history.billing_additions) == 1
    assert history.billing_additions[0].code.value == "140000110"
    assert history.billing_additions[0].name.value == "特定薬剤管理指導加算２"
    assert history.imported_at is not None
    assert history.imported_at.value == fixture.clock.now()
    assert history.counselor_id is None
    assert history.counseled_at is None
    assert not hasattr(history, "importer_staff_id")


@pytest.mark.asyncio
async def test_tc15_同一の明示資格を別処方で再受信しても資格を増やさない() -> None:
    """給付割合まで確定した同一資格は再利用し、別処方ごとに選択履歴を残す。"""
    fixture = await create_fixture()
    insurance = NsipsInsuranceInfo(
        insurer_number="138001",
        insured_symbol="記号B",
        insured_number="番号456",
        branch_number="01",
        insured_type="self",
        benefit_ratio=70,
    )
    first_bundle = _patient_bundle(
        external_patient_id="P-REUSED-COVERAGE",
        document_number="DOC-RPT-01",
        gender="2",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=insurance,
    )
    res1 = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=first_bundle,
        ),
    )

    patient_id_str = res1.patient_id
    coverages_after_first = await fixture.patient_coverage_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(patient_id_str),
    )
    assert len(coverages_after_first) == 1

    second_bundle = _patient_bundle(
        external_patient_id="P-REUSED-COVERAGE",
        document_number="DOC-RPT-02",
        gender="2",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=insurance,
    )
    res2 = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=second_bundle,
        ),
    )

    coverages_after_second = await fixture.patient_coverage_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(patient_id_str),
    )
    # 資格は再利用されるため増えない
    assert len(coverages_after_second) == 1
    assert coverages_after_second[0].id == coverages_after_first[0].id
    # ただし選択履歴は別で起票される
    assert res1.coverage_selection_record_id != res2.coverage_selection_record_id
    assert len(fixture.coverage_selection_repo.items) == 2


@pytest.mark.asyncio
async def test_処方箋の使用期間を過ぎた調剤日は拒否される() -> None:
    """処方箋の使用期間を過ぎた調剤を拒否する。"""
    fixture = await create_fixture()
    # 交付日 9/10 に対し、調剤日 9/22 は期限切れ（9/13まで有効）
    text = (
        "1,20260910,DOC-EXPIRED-01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-2003,サトウジロウ,佐藤次郎,1,19750303\n"
        "4,20260922,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text=text,
    )

    with pytest.raises(DispensingOutsidePrescriptionPeriodError):
        await execute_structured_test_command(fixture, cmd)


@pytest.mark.asyncio
async def test_tc17_調剤日欠損は書込み前に拒否される() -> None:
    """調剤日が無いBundleは拒否し、患者や処方などを先行保存しない。"""
    fixture = await create_fixture()
    bundle = _patient_bundle(
        external_patient_id="P-MISSING-DISPENSED-DATE",
        document_number="DOC-MISSING-DISPENSED-DATE",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
    )
    bundle = replace(bundle, dispensed_date=None)

    with pytest.raises(Exception, match="調剤日"):
        await execute_structured_test_command(
            fixture,
            IngestNsipsCommand(
                corporate_id=str(fixture.corporate_id.value),
                store_id=str(fixture.store_id.value),
                operator_staff_id=str(fixture.pharmacist_id.value),
                structured_bundle=bundle,
            ),
        )

    assert fixture.patient_repo.items == {}
    assert fixture.patient_external_id_repo.items == {}
    assert fixture.patient_coverage_repo.items == {}
    assert fixture.coverage_selection_repo.items == {}
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}
    assert fixture.medication_history_repo.items == {}


def _patient_bundle(
    *,
    external_patient_id: str,
    document_number: str,
    gender: str,
    postal_code: str,
    address: str,
    phone_number: str,
    insurance: NsipsInsuranceInfo | None = None,
    additions: tuple[NsipsAdditionInfo, ...] = (),
) -> NsipsBundle:
    """患者属性を検証する構造化入力を組み立てる。"""
    return NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id=external_patient_id,
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender=gender,
            postal_code=postal_code,
            address=address,
            phone_number=phone_number,
        ),
        prescription=NsipsPrescriptionInfo(
            document_number=document_number,
            issued_date=date(2026, 9, 20),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日1回",
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
        dispensed_date=date(2026, 9, 20),
        insurance=insurance,
        additions=additions,
    )


@pytest.mark.asyncio
async def test_tc25_患者属性がPatient登録と取得DTOまで保持される() -> None:
    """受信した性別コードと連絡先をPatientの登録・取得でそのまま返す。"""
    fixture = await create_fixture()
    access = create_vendor_corporate_access_for(fixture.corporate_repo)
    register_patient = RegisterPatientUseCase(fixture.patient_repo, access)
    bundle = _patient_bundle(
        external_patient_id="P-DEMOGRAPHICS-1",
        document_number="DOC-DEMOGRAPHICS-1",
        gender="7",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
    )
    command = NsipsDataMapper.to_patient_command(
        bundle,
        corporate_id=str(fixture.corporate_id.value),
    )

    patient_id = await register_patient.execute(command)
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=patient_id,
    )
    assert patient is not None
    assert patient.gender is not None and patient.gender.value == "7"
    assert patient.postal_code is not None and patient.postal_code.value == "0012345"
    assert (
        patient.address is not None
        and patient.address.value == "東京都千代田区一丁目2番地"
    )
    assert (
        patient.phone_number is not None
        and patient.phone_number.value == "03-1234-5678"
    )

    query = GetPatientUseCase(fixture.patient_repo, access)
    dto = await query.execute(
        GetPatientQuery(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(patient_id.value),
        )
    )
    assert getattr(dto, "gender", None) == "7"
    assert getattr(dto, "postal_code", None) == "0012345"
    assert getattr(dto, "address", None) == "東京都千代田区一丁目2番地"
    assert getattr(dto, "phone_number", None) == "03-1234-5678"


@pytest.mark.asyncio
async def test_tc26_既存患者の非欠損プロフィール差分をマスターへ反映する() -> None:
    """別受付で受けたプロフィール変更を現行値と受信履歴へ反映する。"""
    fixture = await create_fixture()
    first_bundle = _patient_bundle(
        external_patient_id="P-DEMOGRAPHICS-2",
        document_number="DOC-DEMOGRAPHICS-2A",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
    )
    second_bundle = _patient_bundle(
        external_patient_id="P-DEMOGRAPHICS-2",
        document_number="DOC-DEMOGRAPHICS-2B",
        gender="2",
        postal_code="0098765",
        address="東京都中央区三丁目4番地",
        phone_number="03-9876-5432",
    )

    first = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=first_bundle,
        ),
    )
    second = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=second_bundle,
        ),
    )

    assert second.patient_id == first.patient_id
    assert second.patient_attribute_conflicts == ()
    assert second.has_pending_correction_review is False
    assert getattr(second, "patient_profile_updated_fields", ()) == (
        "patient.gender",
        "patient.postal_code",
        "patient.address",
        "patient.phone_number",
    )
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(first.patient_id),
    )
    assert patient is not None
    assert patient.gender is not None and patient.gender.value == "2"
    assert patient.postal_code is not None and patient.postal_code.value == "0098765"
    assert (
        patient.address is not None
        and patient.address.value == "東京都中央区三丁目4番地"
    )
    assert (
        patient.phone_number is not None
        and patient.phone_number.value == "03-9876-5432"
    )
    profile_change = patient.profile_history[-1]
    assert profile_change.received_profile is not None
    assert profile_change.received_profile.address is not None
    assert profile_change.received_profile.address.value == "東京都中央区三丁目4番地"


@pytest.mark.parametrize(
    ("first_branch", "second_branch"),
    (("01", "02"), ("01", None), (None, "01")),
)
@pytest.mark.asyncio
async def test_tc11_tc12_枝番不一致または欠損時に既存資格を選択しない(
    first_branch: str | None,
    second_branch: str | None,
) -> None:
    """枝番の値と欠損を区別し、競合時に別枝番の資格を誤選択しない。"""
    fixture = await create_fixture()

    def bundle(document_number: str, branch_number: str | None) -> NsipsBundle:
        return _patient_bundle(
            external_patient_id="P-BRANCH-MISMATCH",
            document_number=document_number,
            gender="1",
            postal_code="0012345",
            address="東京都千代田区一丁目2番地",
            phone_number="03-1234-5678",
            insurance=NsipsInsuranceInfo(
                insurer_number="138001",
                insured_symbol="記号A",
                insured_number="番号123",
                branch_number=branch_number,
                insured_type="self",
                benefit_ratio=70,
            ),
        )

    first = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=bundle("DOC-BRANCH-1", first_branch),
        ),
    )
    assert first.coverage_selection_record_id is not None

    with pytest.raises(CoveragePeriodConflictError):
        await execute_structured_test_command(
            fixture,
            IngestNsipsCommand(
                corporate_id=str(fixture.corporate_id.value),
                store_id=str(fixture.store_id.value),
                operator_staff_id=str(fixture.pharmacist_id.value),
                structured_bundle=bundle("DOC-BRANCH-2", second_branch),
            ),
        )

    assert len(fixture.patient_coverage_repo.items) == 1
    assert len(fixture.coverage_selection_repo.items) == 1


@pytest.mark.asyncio
async def test_tc13_公費の順位違いを既存の別順位資格へ誤照合しない() -> None:
    """同じ公費番号を第一・第二順位で受けても両順位の資格を維持する。"""
    fixture = await create_fixture()

    first_bundle = _patient_bundle(
        external_patient_id="P-PUBLIC-PRIORITY",
        document_number="DOC-PUBLIC-1",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=NsipsInsuranceInfo(
            insurer_number="",
            insured_symbol="",
            insured_number="",
            public_payer_number_1="54130012",
            public_recipient_number_1="1234567",
        ),
    )
    second_bundle = _patient_bundle(
        external_patient_id="P-PUBLIC-PRIORITY",
        document_number="DOC-PUBLIC-2",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=NsipsInsuranceInfo(
            insurer_number="",
            insured_symbol="",
            insured_number="",
            public_payer_number_1="54130012",
            public_recipient_number_1="1234567",
            public_payer_number_2="54130012",
            public_recipient_number_2="1234567",
        ),
    )

    first = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=first_bundle,
        ),
    )
    assert first.coverage_selection_record_id is not None

    try:
        second = await execute_structured_test_command(
            fixture,
            IngestNsipsCommand(
                corporate_id=str(fixture.corporate_id.value),
                store_id=str(fixture.store_id.value),
                operator_staff_id=str(fixture.pharmacist_id.value),
                structured_bundle=second_bundle,
            ),
        )
    except ReceptionCoverageSelectionError:
        # 重複して渡された第一順位IDで組み合わせ検証が止まる実装も、誤照合を示す。
        second = None

    coverages = await fixture.patient_coverage_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(first.patient_id),
    )
    assert {coverage.priority.value for coverage in coverages} == {1, 2}
    assert second is not None
    assert second.coverage_selection_record_id is not None
    selection = await fixture.coverage_selection_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=CoverageSelectionRecordId.parse(second.coverage_selection_record_id),
    )
    assert selection is not None
    selected_ids = {str(item.value) for item in selection.source_coverage_ids}
    assert {str(item.id.value) for item in coverages} <= selected_ids


@pytest.mark.asyncio
async def test_tc10_給付割合不明の資格を保持し請求選択しない() -> None:
    """給付割合を推測せず資格台帳へ保持し、選択できない理由を返す。"""
    fixture = await create_fixture()
    bundle = _patient_bundle(
        external_patient_id="P-UNKNOWN-BENEFIT-RATIO",
        document_number="DOC-UNKNOWN-BENEFIT-RATIO",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="記号U",
            insured_number="番号100",
            branch_number="01",
            insured_type=None,
            benefit_ratio=None,
        ),
    )

    try:
        result = await execute_structured_test_command(
            fixture,
            IngestNsipsCommand(
                corporate_id=str(fixture.corporate_id.value),
                store_id=str(fixture.store_id.value),
                operator_staff_id=str(fixture.pharmacist_id.value),
                structured_bundle=bundle,
            ),
        )
    except Exception as error:
        pytest.fail(f"給付割合不明を資格として保持できなかった: {error}")

    coverages = await fixture.patient_coverage_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(result.patient_id),
    )
    assert len(coverages) == 1
    assert coverages[0].insurance_details is not None
    assert coverages[0].insurance_details.benefit_ratio is None
    assert result.coverage_selection_record_id is None
    assert getattr(result, "coverage_review_required", False) is True
    assert getattr(result, "coverage_review_reason", None) == "benefit_ratio_missing"


@pytest.mark.asyncio
async def test_tc14_公費の片側欠損を登録せず要確認理由を返す() -> None:
    """負担者・受給者番号の片側欠損を有効資格にせず要確認で返す。"""
    fixture = await create_fixture()
    bundle = _patient_bundle(
        external_patient_id="P-INCOMPLETE-PUBLIC-COVERAGE",
        document_number="DOC-INCOMPLETE-PUBLIC-COVERAGE",
        gender="1",
        postal_code="0012345",
        address="東京都千代田区一丁目2番地",
        phone_number="03-1234-5678",
        insurance=NsipsInsuranceInfo(
            insurer_number="",
            insured_symbol="",
            insured_number="",
            public_payer_number_1="54130012",
            public_recipient_number_1=None,
        ),
    )

    result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            structured_bundle=bundle,
        ),
    )

    assert fixture.patient_coverage_repo.items == {}
    assert result.coverage_selection_record_id is None
    assert getattr(result, "coverage_review_required", False) is True
    assert (
        getattr(result, "coverage_review_reason", None) == "public_expense_incomplete"
    )
