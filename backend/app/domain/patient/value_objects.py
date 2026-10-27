"""patientの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import (
    ExternalPatientId,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientHeadingText,
    PatientHeadingTimestamp,
    PatientPhoneNumber,
    PatientPostalCode,
    PatientProfileChangeSource,
    PatientProfileField,
    PatientStatus,
    PatientStatusReason,
)
from app.domain.reception.identifiers import ReceptionId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class PatientHeadingContent(ValueObject):
    """患者サマリと申し送り本文の現在値。"""

    summary: PatientHeadingText | None
    notes: PatientHeadingText | None


@dataclass(frozen=True, kw_only=True)
class PatientHeadingRevision(ValueObject):
    """記録者・記録時刻と内容を束ねた追記型改訂。"""

    content: PatientHeadingContent
    person_id: AccountPersonId
    account_id: UserAccountId
    recorded_at: PatientHeadingTimestamp


@dataclass(frozen=True, kw_only=True)
class PatientStatusChange(ValueObject):
    """患者の状態変更履歴記録。"""

    before: PatientStatus
    after: PatientStatus
    reason: PatientStatusReason
    person_id: AccountPersonId
    account_id: UserAccountId
    recorded_at: datetime
    merged_into_id: PatientId | None = None

    def validate(self) -> None:
        if self.recorded_at.utcoffset() is None:
            raise DomainValidationError("記録日時にはタイムゾーンが必要です。")
        if self.after == PatientStatus.MERGED and self.merged_into_id is None:
            raise DomainValidationError("統合先患者IDが必要です。")
        if self.after != PatientStatus.MERGED and self.merged_into_id is not None:
            raise DomainValidationError("統合先患者IDは指定できません。")


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
    changed_fields: tuple[PatientProfileField, ...]
    source: PatientProfileChangeSource = PatientProfileChangeSource.NSIPS
    reception_id: ReceptionId | None = None
    store_id: StoreId | None = None
    external_patient_id: ExternalPatientId | None = None
    received_profile: PatientProfileSnapshot | None = None
    before_profile: PatientProfileSnapshot | None = None
    applied_profile: PatientProfileSnapshot | None = None
    person_id: AccountPersonId | None = None
    account_id: UserAccountId | None = None
