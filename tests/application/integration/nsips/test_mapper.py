"""NSIPSデータマッパーの単体テスト (TC-12〜TC-15)。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.integration.nsips.mapper import NsipsDataMapper
from app.application.integration.nsips.models import (
    NsipsBundle,
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
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤 医師",
            rps=rps,
            split_info=split_info,
        ),
    )


def test_患者登録入力へのマッピングと性別正規化() -> None:
    """TC-12: NsipsBundleから患者登録コマンドへマッピングされ、氏名が正しく分割される。"""
    mapper = NsipsDataMapper()

    bundle = _create_sample_bundle(gender="1")
    cmd = mapper.to_patient_command(bundle, corporate_id="corp-1")
    assert cmd.last_name == "山田"
    assert cmd.first_name == "太郎"
    assert cmd.last_name_kana == "ヤマダ"
    assert cmd.first_name_kana == "タロウ"
    assert cmd.birth_date == date(1980, 5, 20)


def test_処方箋登録コマンドへのマッピング() -> None:
    """TC-13: NsipsBundleから処方箋登録コマンドへ正しくマッピングされる。"""
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
    """TC-14: 通常処方および分割処方から調剤開始コマンドへ正しくマッピングされる。"""
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


def test_薬歴下書き起票コマンドへのマッピングとSOAP初期化() -> None:
    """TC-15: NsipsBundleから薬歴下書き起票コマンドへマッピングされ、O情報および手帳・残薬が初期化される。"""
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
    assert cmd.method == "face_to_face"
    assert len(cmd.soap.objective) == 1
    assert "アムロジピン錠5mg" in cmd.soap.objective[0].text
    assert cmd.handbook_status.presented is True
    assert cmd.residual_drug.has_residual_drugs is False
