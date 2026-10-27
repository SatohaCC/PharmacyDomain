"""患者集約の基本振る舞い・不変条件テスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import Patient
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import (
    ExternalPatientId,
    PatientBirthDate,
    PatientNumber,
    PatientProfileField,
    PatientStatus,
)
from app.domain.patient.value_objects import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
from app.domain.reception.identifiers import ReceptionId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.store.identifiers import StoreId


def _create_patient() -> Patient:
    return Patient(
        id=PatientId.generate(),
        corporate_id=CorporateId.generate(),
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
        patient_number=PatientNumber(1),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
        gender=None,
        postal_code=None,
        address=None,
        phone_number=None,
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


def test_tc67_同じ受付IDでも店舗ごとにプロフィール履歴を保持する() -> None:
    """法人内で重なる受付IDを別店舗の受信履歴としてそれぞれ記録する。"""
    patient = _create_patient()
    assert patient.birth_date is not None
    reception_id = ReceptionId.generate()
    recorded_at = datetime(2026, 9, 24, 1, 2, 3, tzinfo=UTC)
    profile = PatientProfileSnapshot(
        names=patient.names,
        birth_date=patient.birth_date,
        gender=None,
        postal_code=None,
        address=None,
        phone_number=None,
    )
    first_store = PatientProfileChange(
        reception_id=reception_id,
        store_id=StoreId.generate(),
        external_patient_id=ExternalPatientId("POS-A"),
        recorded_at=recorded_at,
        changed_fields=tuple(
            PatientProfileField(item) for item in ("patient.address",)
        ),
        received_profile=profile,
    )
    second_store = PatientProfileChange(
        reception_id=reception_id,
        store_id=StoreId.generate(),
        external_patient_id=ExternalPatientId("POS-B"),
        recorded_at=recorded_at,
        changed_fields=tuple(
            PatientProfileField(item) for item in ("patient.address",)
        ),
        received_profile=profile,
    )

    updated = patient.record_profile_change(first_store).record_profile_change(
        second_store
    )

    assert updated.profile_history == (first_store, second_store)
