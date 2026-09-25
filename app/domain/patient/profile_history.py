"""外部連携で受信した患者プロフィールの追記履歴。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.identity.primitives import AccountPersonId, UserAccountId
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


class PatientProfileChangeSource(StrEnum):
    """患者プロフィール変更の記録元。"""

    NSIPS = "nsips"
    MANUAL = "manual"


@dataclass(frozen=True, kw_only=True)
class PatientProfileSnapshot:
    """患者プロフィールのある時点の値。"""

    names: PersonNames
    birth_date: PatientBirthDate | None
    gender: PatientGenderCode | None
    postal_code: PatientPostalCode | None
    address: PatientAddress | None
    phone_number: PatientPhoneNumber | None


@dataclass(frozen=True, kw_only=True)
class PatientProfileChange:
    """受付受信または手動更新で生じたプロフィール変更の証跡。"""

    recorded_at: datetime
    changed_fields: tuple[str, ...]
    source: PatientProfileChangeSource = PatientProfileChangeSource.NSIPS
    reception_id: ReceptionId | None = None
    store_id: StoreId | None = None
    external_patient_id: ExternalPatientId | None = None
    received_profile: PatientProfileSnapshot | None = None
    before_profile: PatientProfileSnapshot | None = None
    applied_profile: PatientProfileSnapshot | None = None
    person_id: AccountPersonId | None = None
    account_id: UserAccountId | None = None
