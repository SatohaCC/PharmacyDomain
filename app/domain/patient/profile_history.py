"""外部連携で受信した患者プロフィールの追記履歴。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.patient.primitives import (
    ExternalPatientId,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.shared.person_name import PersonNames
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class PatientProfileSnapshot:
    """受信時点の患者プロフィール値。"""

    names: PersonNames
    birth_date: PatientBirthDate
    gender: PatientGenderCode | None
    postal_code: PatientPostalCode | None
    address: PatientAddress | None
    phone_number: PatientPhoneNumber | None


@dataclass(frozen=True, kw_only=True)
class PatientProfileChange:
    """受付で受信したプロフィール変更の証跡。"""

    reception_id: ReceptionId
    store_id: StoreId
    external_patient_id: ExternalPatientId
    recorded_at: datetime
    changed_fields: tuple[str, ...]
    received_profile: PatientProfileSnapshot
