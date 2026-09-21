"""NSIPSパーサーの単体テスト (TC-01〜TC-11)。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.integration.nsips.exceptions import NsipsParseError
from app.application.integration.nsips.parser import NsipsParser

_SAMPLE_NSIPS_STANDARD = """
1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師
2,P-1001,ヤマダタロウ,山田太郎,1,19800101,1000001,東京都千代田区1-1,03-1111-2222
5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン錠5mg,1.0,錠,0
5,2,外用,1日1回就寝前,1,1,620000001,モーラステープ20mg,7.0,枚,0
"""

_SAMPLE_NSIPS_SPLIT = """
1,20260921,DOC-002,1310001,中央診療所,01,内科,佐藤医師
2,P-1002,スズキハナコ,鈴木花子,2,19900515
5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン錠5mg,1.0,錠,0
6,2,3,長期保存が困難なため
"""

_SAMPLE_NSIPS_MULTI_MEDICINE = """
1,20260921,DOC-003,1310001,中央診療所,,佐藤医師
2,P-1003,タナカイチロウ,田中一郎,1,19750820
5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン錠5mg,1.0,錠,0
5,1,内服,1日3回毎食後,14,2,610406002,アトルバスタチン錠10mg,1.0,錠,0
"""

_SAMPLE_NSIPS_PREPARATION = """
1,20260921,DOC-004,1310001,中央診療所,01,内科,佐藤医師
2,P-1004,タナカハナコ,田中花子,2,19650310
5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン錠5mg,1.0,錠,1
"""

_SAMPLE_NSIPS_ZERO_MEDICINE = """
1,20260921,DOC-005,1310001,中央診療所,01,内科,佐藤医師
2,P-1005,サイトウケンジ,斉藤健二,1,19551201
"""


def test_標準的な処方NSIPSテキストを正しくパースできる() -> None:
    """TC-01: 標準的な処方データ（基本、患者、Rp2件、薬品各1件）を正しくパースできる。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_STANDARD)

    assert bundle.prescription.document_number == "DOC-001"
    assert bundle.prescription.issued_date == date(2026, 9, 21)
    assert bundle.prescription.institution_code == "1310001"
    assert bundle.prescription.institution_name == "中央診療所"
    assert bundle.prescription.doctor_name == "佐藤医師"

    assert bundle.patient.external_patient_id == "P-1001"
    assert bundle.patient.kanji_name == "山田太郎"
    assert bundle.patient.kana_name == "ヤマダタロウ"
    assert bundle.patient.gender == "1"
    assert bundle.patient.birth_date == date(1980, 1, 1)

    assert len(bundle.prescription.rps) == 2
    rp1 = bundle.prescription.rps[0]
    assert rp1.rp_number == 1
    assert rp1.group_name == "内服"
    assert rp1.instructions == "1日3回毎食後"
    assert rp1.dispensing_quantity == 14
    assert len(rp1.medicines) == 1
    assert rp1.medicines[0].medicine_code == "610406001"
    assert rp1.medicines[0].dosage == Decimal("1.0")
    assert rp1.medicines[0].unit == "錠"


def test_患者連絡先および診療科等の任意項目がパースされる() -> None:
    """TC-02: 患者の任意項目（郵便番号、住所、電話番号）および診療科がパースされる。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_STANDARD)

    assert bundle.patient.postal_code == "1000001"
    assert bundle.patient.address == "東京都千代田区1-1"
    assert bundle.patient.phone_number == "03-1111-2222"
    assert bundle.prescription.department_code == "01"
    assert bundle.prescription.department_name == "内科"


def test_分割調剤情報レコードが正しくパースされる() -> None:
    """TC-03: 分割調剤レコード（6レコード）が正しくパースされる。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_SPLIT)

    assert bundle.prescription.split_info is not None
    assert bundle.prescription.split_info.iteration == 2
    assert bundle.prescription.split_info.total_split_count == 3
    assert bundle.prescription.split_info.split_reason == "長期保存が困難なため"


def test_同一Rp番号の複数薬品がグループ化される() -> None:
    """TC-04: 同一Rp番号の複数薬品が1つのRpにグループ化される。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_MULTI_MEDICINE)

    assert len(bundle.prescription.rps) == 1
    rp = bundle.prescription.rps[0]
    assert rp.rp_number == 1
    assert len(rp.medicines) == 2
    assert rp.medicines[0].medicine_name == "アムロジピン錠5mg"
    assert rp.medicines[1].medicine_name == "アトルバスタチン錠10mg"


def test_調製区分フラグから調製方法が導出される() -> None:
    """TC-05: 調製区分フラグ（1:一包化）から調製方法が導出される。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_PREPARATION)

    assert bundle.prescription.rps[0].preparation_method == "PACKAGE_UNIT"


def test_空白トリムおよび改行コードの違いを許容する() -> None:
    """TC-06: 余計な空白やCRLF改行が混在していても正常にパースできる。"""
    raw = "\r\n  1 , 20260921 , DOC-006 , 1310001 , 中央診療所 , 01 , 内科 , 佐藤医師 \r\n\r\n 2 , P-1006 , ヤマダ , 山田 , 1 , 19800101 \r\n"
    parser = NsipsParser()
    bundle = parser.parse(raw)

    assert bundle.prescription.document_number == "DOC-006"
    assert bundle.patient.external_patient_id == "P-1006"


def test_日付文字列が正しくdate型に変換される() -> None:
    """TC-07: YYYYMMDD形式の日付文字列が正確にdateオブジェクトへ変換される。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_STANDARD)

    assert bundle.prescription.issued_date == date(2026, 9, 21)
    assert bundle.patient.birth_date == date(1980, 1, 1)


def test_必須レコード欠落でパース例外になる() -> None:
    """TC-08: 処方基本または患者レコードが欠落している場合、NsipsParseErrorを送出する。"""
    parser = NsipsParser()
    with pytest.raises(NsipsParseError, match="処方基本レコード"):
        parser.parse("2,P-1001,ヤマダ,山田,1,19800101\n")

    with pytest.raises(NsipsParseError, match="患者レコード"):
        parser.parse("1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n")


def test_必須フィールド空でパース例外になる() -> None:
    """TC-09: 処方箋番号や患者番号等の必須列が空文字の場合、NsipsParseErrorを送出する。"""
    raw = """
1,20260921,,1310001,中央診療所,01,内科,佐藤医師
2,P-1001,ヤマダ,山田,1,19800101
"""
    parser = NsipsParser()
    with pytest.raises(NsipsParseError, match="処方箋番号"):
        parser.parse(raw)


def test_不正日付形式でパース例外になる() -> None:
    """TC-10: 不正な日付文字列の場合、NsipsParseErrorを送出する。"""
    raw = """
1,20261399,DOC-001,1310001,中央診療所,01,内科,佐藤医師
2,P-1001,ヤマダ,山田,1,19800101
"""
    parser = NsipsParser()
    with pytest.raises(NsipsParseError, match="日付"):
        parser.parse(raw)


def test_薬品明細が0件のフォローアップ受付NSIPSを正常にパースできる() -> None:
    """TC-11: 薬品明細が0件の受付データ（フォローアップ・指導料のみ）でもrps=()として正常にパースできる。"""
    parser = NsipsParser()
    bundle = parser.parse(_SAMPLE_NSIPS_ZERO_MEDICINE)

    assert bundle.prescription.document_number == "DOC-005"
    assert bundle.patient.external_patient_id == "P-1005"
    assert bundle.prescription.rps == ()
