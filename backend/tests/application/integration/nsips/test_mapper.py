"""NSIPSデータマッパーの単体テスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.integration.boundary_models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)
from app.application.integration.commands.services.mapper import NsipsDataMapper


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


def test_tc11_NSIPSデータマッパーは処方調剤薬歴Commandを作らない() -> None:
    """NSIPSデータマッパーは処方・調剤・薬歴のCommandを自動生成しない。"""
    mapper = NsipsDataMapper()
    assert not hasattr(mapper, "to_medication_history_command")
    assert not hasattr(mapper, "to_prescription_command")
    assert not hasattr(mapper, "to_dispensing_command")
