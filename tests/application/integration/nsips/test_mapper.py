"""NSIPSデータマッパーの単体テスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.integration.nsips.mapper import NsipsDataMapper
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


def _create_sample_bundle(
    *,
    gender: str = "1",
    split_info: NsipsSplitInfo | None = None,
    rps: tuple[NsipsRpInfo, ...] | None = None,
    dispensed_date: date | None = date(2026, 9, 22),
    insurance: NsipsInsuranceInfo | None = None,
    additions: tuple[NsipsAdditionInfo, ...] = (),
    department_code: str | None = "01",
    department_name: str | None = "内科",
    institution_code: str = "1310001",
    doctor_kana: str | None = None,
) -> NsipsBundle:
    if rps is None:
        rps = (
            NsipsRpInfo(
                rp_number=1,
                group_name="内服",
                instructions="1日3回毎食後",
                dispensing_quantity=14,
                medicines=(
                    NsipsMedicineInfo(
                        medicine_code="610406001",
                        medicine_name="アムロジピン錠5mg",
                        dosage=Decimal("1.0"),
                        unit="錠",
                    ),
                ),
                preparation_method="PACKAGE_UNIT",
            ),
        )

    return NsipsBundle(
        header_version="1.0",
        patient=NsipsPatientInfo(
            external_patient_id="P-001",
            kanji_name="山田 太郎",
            kana_name="ヤマダ タロウ",
            birth_date=date(1980, 5, 20),
            gender=gender,
            postal_code="1000001",
            address="東京都千代田区1-1",
            phone_number="03-1111-2222",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-999",
            issued_date=date(2026, 9, 21),
            institution_code=institution_code,
            institution_name="中央診療所",
            department_code=department_code,
            department_name=department_name,
            doctor_name="佐藤 医師",
            doctor_kana=doctor_kana,
            rps=rps,
            split_info=split_info,
        ),
        dispensed_date=dispensed_date,
        insurance=insurance,
        additions=additions,
    )


def test_tc25_患者属性を新規登録Commandへそのまま写す() -> None:
    """性別コード、郵便番号、住所、電話を加工せず患者登録入力へ渡す。"""
    mapper = NsipsDataMapper()

    bundle = _create_sample_bundle(gender="1")
    cmd = mapper.to_patient_command(bundle, corporate_id="corp-1")
    assert cmd.last_name == "山田"
    assert cmd.first_name == "太郎"
    assert cmd.last_name_kana == "ヤマダ"
    assert cmd.first_name_kana == "タロウ"
    assert cmd.birth_date == date(1980, 5, 20)
    assert getattr(cmd, "gender", None) == "1"
    assert getattr(cmd, "postal_code", None) == "1000001"
    assert getattr(cmd, "address", None) == "東京都千代田区1-1"
    assert getattr(cmd, "phone_number", None) == "03-1111-2222"


def test_処方箋登録コマンドへのマッピング() -> None:
    """NsipsBundleから提供済みの処方情報が登録コマンドへ写される。"""
    mapper = NsipsDataMapper()
    bundle = _create_sample_bundle()

    cmd = mapper.to_prescription_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        patient_id="pat-1",
    )

    assert cmd.corporate_id == "corp-1"
    assert cmd.store_id == "store-1"
    assert cmd.patient_id == "pat-1"
    assert cmd.document_number == "DOC-999"
    assert cmd.issued_date == date(2026, 9, 21)
    assert cmd.medical_institution.code == "1310001"
    assert cmd.medical_institution.name == "中央診療所"
    assert cmd.department.code == "01"
    assert cmd.department.name == "内科"
    assert cmd.prescriber.last_name == "佐藤"
    assert cmd.prescriber.first_name == "医師"

    assert len(cmd.rps) == 1
    rp = cmd.rps[0]
    assert rp.rp_number == 1
    assert rp.dosage_instruction.name == "1日3回毎食後"
    assert rp.quantity == 14
    assert len(rp.medicines) == 1
    assert rp.medicines[0].name == "アムロジピン錠5mg"
    assert rp.medicines[0].amount == "1.0"
    assert rp.medicines[0].unit == "錠"


def test_調剤開始コマンドへのマッピングと分割情報() -> None:
    """通常処方および分割処方から調剤開始コマンドへ正しくマッピングされる。"""
    mapper = NsipsDataMapper()

    # 通常処方
    bundle_normal = _create_sample_bundle()
    cmd_normal = mapper.to_dispensing_command(
        bundle_normal,
        corporate_id="corp-1",
        store_id="store-1",
        prescription_id="presc-1",
        dispenser_id="staff-1",
    )
    assert cmd_normal.iteration == 1
    assert cmd_normal.dispensed_date == date(2026, 9, 22)
    assert cmd_normal.total_split_count is None
    assert cmd_normal.split_reason is None
    assert len(cmd_normal.dispensed_rps) == 1
    assert cmd_normal.dispensed_rps[0].medicines[0].preparations == (
        "unit_dose_packaged",
    )

    # 分割処方
    split = NsipsSplitInfo(
        iteration=2, total_split_count=3, split_reason="長期保存が困難なため"
    )
    bundle_split = _create_sample_bundle(split_info=split)
    cmd_split = mapper.to_dispensing_command(
        bundle_split,
        corporate_id="corp-1",
        store_id="store-1",
        prescription_id="presc-1",
        dispenser_id="staff-1",
    )
    assert cmd_split.iteration == 2
    assert cmd_split.total_split_count == 3
    assert cmd_split.split_reason == "long_term_storage"


def test_tc20_未確認事項を薬歴下書きで不明のままにする() -> None:
    """NSIPS取込だけでは指導方法や確認結果を事実として作らない。"""
    mapper = NsipsDataMapper()
    bundle = _create_sample_bundle()

    cmd = mapper.to_medication_history_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        dispensing_id="disp-1",
        counselor_id="staff-1",
    )

    assert cmd.corporate_id == "corp-1"
    assert cmd.store_id == "store-1"
    assert cmd.dispensing_id == "disp-1"
    assert cmd.counselor_id == "staff-1"
    assert cmd.method is None
    assert len(cmd.soap.objective) == 1
    assert "アムロジピン錠5mg" in cmd.soap.objective[0].text
    assert cmd.handbook_status is None
    assert cmd.residual_drug is None
    assert cmd.information_sheet_provided is None


def test_tc08_保険区分と給付割合の不明を既定値で埋めない() -> None:
    """保険区分と給付割合が欠損しているとき、本人・70%を合成しない。"""
    bundle = _create_sample_bundle(
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="記号A",
            insured_number="番号123",
            insured_type=None,
            benefit_ratio=None,
        )
    )

    [command] = NsipsDataMapper.to_coverage_commands(
        bundle,
        corporate_id="corp-1",
        patient_id="pat-1",
    )

    assert command.insured_type is None
    assert command.benefit_ratio is None


def test_tc16_調剤日を調剤と資格適用に使い処方日は維持する() -> None:
    """処方日と異なる調剤日を調剤日・資格適用日に写す。"""
    bundle = _create_sample_bundle(
        insurance=NsipsInsuranceInfo(
            insurer_number="138001",
            insured_symbol="記号A",
            insured_number="番号123",
        )
    )

    prescription = NsipsDataMapper.to_prescription_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        patient_id="pat-1",
    )
    dispensing = NsipsDataMapper.to_dispensing_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        prescription_id="presc-1",
        dispenser_id="staff-1",
    )
    [coverage] = NsipsDataMapper.to_coverage_commands(
        bundle,
        corporate_id="corp-1",
        patient_id="pat-1",
    )

    assert prescription.issued_date == date(2026, 9, 21)
    assert dispensing.dispensed_date == date(2026, 9, 22)
    assert coverage.valid_from == date(2026, 9, 22)
    assert coverage.activated_on == date(2026, 9, 22)


def test_tc17_調剤日が無い場合に処方日を代用しない() -> None:
    """調剤日欠損時は、処方日で調剤コマンドを成立させない。"""
    bundle = _create_sample_bundle(dispensed_date=None)

    command = NsipsDataMapper.to_dispensing_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        prescription_id="presc-1",
        dispenser_id="staff-1",
    )

    assert command.dispensed_date is None


def test_tc19_根拠の無い診療科_医師カナ_都道府県を補完しない() -> None:
    """未提供の診療科・医師カナ・都道府県を固定値やコード推測で作らない。"""
    bundle = _create_sample_bundle(
        department_code=None,
        department_name=None,
        institution_code="9912345",
    )

    command = NsipsDataMapper.to_prescription_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        patient_id="pat-1",
    )

    assert command.department.code is None
    assert command.department.name is None
    assert command.prescriber.last_name_kana is None
    assert command.prescriber.first_name_kana is None
    assert command.medical_institution.prefecture_code is None


def test_tc18_提供された処方医カナを保持する() -> None:
    """提供された医師カナだけを処方箋登録入力へ写す。"""
    bundle = _create_sample_bundle(doctor_kana="ヤマダ ハナコ")

    command = NsipsDataMapper.to_prescription_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        patient_id="pat-1",
    )

    assert command.prescriber.last_name_kana == "ヤマダ"
    assert command.prescriber.first_name_kana == "ハナコ"


def test_tc24_保険と算定事実を薬歴の臨床記載へ混ぜない() -> None:
    """受信保険と算定加算はSOAPの臨床記載へ転記しない。"""
    bundle = _create_sample_bundle(
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
                quantity=2,
            ),
        ),
    )

    command = NsipsDataMapper.to_medication_history_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        dispensing_id="disp-1",
        counselor_id="staff-1",
    )
    objective = "\n".join(note.text for note in command.soap.objective)

    assert "保険情報:" not in objective
    assert "特定薬剤管理指導加算２" not in objective
    assert len(command.billing_additions or ()) == 1


def test_tc27_加算の点数と数量を別々に保持する() -> None:
    """加算コード・名称に対応する点数と数量をコマンドで保持する。"""
    bundle = _create_sample_bundle(
        additions=(
            NsipsAdditionInfo(
                code="140000110",
                name="特定薬剤管理指導加算２",
                points=100,
                quantity=2,
            ),
        ),
    )

    command = NsipsDataMapper.to_medication_history_command(
        bundle,
        corporate_id="corp-1",
        store_id="store-1",
        dispensing_id="disp-1",
        counselor_id="staff-1",
    )

    [addition] = command.billing_additions or ()
    assert addition.code == "140000110"
    assert addition.name == "特定薬剤管理指導加算２"
    assert getattr(addition, "points", None) == 100
    assert getattr(addition, "quantity", None) == 2
