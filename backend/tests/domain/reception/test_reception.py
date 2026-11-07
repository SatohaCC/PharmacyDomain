"""Reception集約の単体テスト。"""

from __future__ import annotations

from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import CurrentRecordFieldId
from app.domain.patient.identifiers import PatientId
from app.domain.reception.entities import Reception
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import (
    CurrentRecordFieldValueText,
    ReceptionFingerprint,
    ReceptionSourceStatus,
)
from app.domain.reception.value_objects import CurrentRecordFieldValue
from app.domain.store.identifiers import StoreId


def test_受付集約_今回記載欄入力値の更新_正常に更新され保持される() -> None:
    """TC-REC-01: 受付の今回記載欄入力値が正常に更新・保持されること。"""
    rec = Reception(
        id=ReceptionId.generate(),
        corporate_id=CorporateId.generate(),
        store_id=StoreId.generate(),
        patient_id=PatientId.generate(),
        latest_fingerprint=ReceptionFingerprint("a" * 64),
        field_fingerprints=(),
        source_status=ReceptionSourceStatus.CURRENT,
    )
    assert rec.current_record_values == ()

    field_id_1 = CurrentRecordFieldId.generate()
    field_id_2 = CurrentRecordFieldId.generate()
    values = (
        CurrentRecordFieldValue(
            field_id=field_id_1,
            value_text=CurrentRecordFieldValueText("体調良好、特に変化なし。"),
        ),
        CurrentRecordFieldValue(
            field_id=field_id_2,
            value_text=CurrentRecordFieldValueText("残薬2日分あり。"),
        ),
    )

    updated = rec.update_current_record_values(values)
    assert len(updated.current_record_values) == 2
    assert (
        updated.current_record_values[0].value_text.value == "体調良好、特に変化なし。"
    )
    assert updated.current_record_values[1].field_id == field_id_2
