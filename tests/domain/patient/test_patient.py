"""患者集約の基本振る舞い・不変条件テスト。"""

from __future__ import annotations

from datetime import date

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.lifecycle import PatientStatus
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientBirthDate, PatientNumber
from app.domain.shared.person_name import PersonNames


def _create_patient() -> Patient:
    return Patient.create(
        corporate_id=CorporateId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
        patient_number=PatientNumber(1),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
    )


def test_TC05_新規作成時の初期状態() -> None:
    # Arrange / Act
    patient = _create_patient()

    # Assert
    assert patient.status == PatientStatus.ACTIVE
    assert patient.merged_into_id is None
    assert patient.status_history == ()
    assert patient.is_active is True
    assert patient.is_merged is False
