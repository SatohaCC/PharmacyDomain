"""保存するNSIPS原本の表現を、明示変換への移行後も保持する。"""

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.application.integration.nsips.ingest_nsips import IngestNsipsUseCase
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


@pytest.mark.parametrize("with_optional", [False, True])
def test_受付原本_明示変換しても_既存のJSON表現を維持する(with_optional: bool) -> None:
    bundle = NsipsBundle(
        header_version="比較用・日本語",
        patient=NsipsPatientInfo(
            external_patient_id="P-1",
            kanji_name="山田 太郎",
            kana_name="ヤマダ タロウ",
            birth_date=date(2000, 1, 2),
            gender=None,
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="001",
            issued_date=date(2026, 10, 17),
            institution_code="001",
            institution_name="病院",
            department_code=None,
            department_name=None,
            doctor_name="医師",
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="朝食後\n服用",
                    dispensing_quantity=7,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="A",
                            medicine_name="薬品",
                            dosage=Decimal("1.250"),
                            unit="錠",
                        ),
                    ),
                ),
            ),
            split_info=(
                NsipsSplitInfo(iteration=1, total_split_count=2, split_reason="long")
                if with_optional
                else None
            ),
        ),
        dispensed_date=date(2026, 10, 18) if with_optional else None,
        insurance=(
            NsipsInsuranceInfo(
                insurer_number="001", insured_symbol="記号", insured_number="123"
            )
            if with_optional
            else None
        ),
        additions=(NsipsAdditionInfo(code="01", name="加算", points=10, quantity=1),)
        if with_optional
        else (),
    )
    imported_at = datetime(2026, 10, 17, 12, 34, 56, 123456, tzinfo=UTC)

    def legacy_encode(value: object) -> str:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(type(value).__name__)

    expected = json.dumps(
        asdict(bundle),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=legacy_encode,
    )

    actual = IngestNsipsUseCase._source_data(
        bundle, imported_at=imported_at, is_follow_up=False
    )

    assert actual.bundle_json == expected
    assert actual.imported_at == imported_at
    parsed = json.loads(actual.bundle_json)
    assert parsed["prescription"]["rps"][0]["medicines"][0]["dosage"] == "1.250"
    assert parsed["patient"]["birth_date"] == "2000-01-02"
    assert parsed["patient"]["gender"] is None
    assert "山田 太郎" in actual.bundle_json
