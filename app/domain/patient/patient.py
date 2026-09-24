"""患者集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.exceptions import PatientStateConflictError
from app.domain.patient.lifecycle import (
    PatientStatus,
    PatientStatusChange,
    PatientStatusReason,
)
from app.domain.patient.primitives import (
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientId,
    PatientNumber,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.profile_history import PatientProfileChange
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames


@dataclass(frozen=True, eq=False, kw_only=True)
class Patient(AggregateRoot[PatientId]):
    """患者エンティティ（集約ルート）。法人単位で管理する患者情報を表す。"""

    id: PatientId
    corporate_id: CorporateId
    names: PersonNames
    patient_number: PatientNumber
    birth_date: PatientBirthDate | None = None
    gender: PatientGenderCode | None = None
    postal_code: PatientPostalCode | None = None
    address: PatientAddress | None = None
    phone_number: PatientPhoneNumber | None = None
    status: PatientStatus = PatientStatus.ACTIVE
    merged_into_id: PatientId | None = None
    status_history: tuple[PatientStatusChange, ...] = ()
    profile_history: tuple[PatientProfileChange, ...] = ()

    def validate(self) -> None:
        """患者集約の不変条件を検証する。"""
        if self.status == PatientStatus.MERGED and self.merged_into_id is None:
            raise DomainValidationError("統合先患者IDが必要です。")
        if self.status != PatientStatus.MERGED and self.merged_into_id is not None:
            raise DomainValidationError("統合先患者IDは指定できません。")
        if self.merged_into_id is not None and self.merged_into_id == self.id:
            raise DomainValidationError("自身へ統合することはできません。")

    @property
    def is_active(self) -> bool:
        """通常業務（受付・調剤等）が可能な状態か。"""
        return self.status == PatientStatus.ACTIVE

    @property
    def is_merged(self) -> bool:
        """他の患者集約へ名寄せ統合された状態か。"""
        return self.status == PatientStatus.MERGED

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        names: PersonNames,
        patient_number: PatientNumber,
        birth_date: PatientBirthDate | None = None,
        gender: PatientGenderCode | None = None,
        postal_code: PatientPostalCode | None = None,
        address: PatientAddress | None = None,
        phone_number: PatientPhoneNumber | None = None,
    ) -> Self:
        """新しい患者を生成する。"""
        return cls(
            id=PatientId.generate(),
            corporate_id=corporate_id,
            names=names,
            patient_number=patient_number,
            birth_date=birth_date,
            gender=gender,
            postal_code=postal_code,
            address=address,
            phone_number=phone_number,
        )

    def change_names(self, names: PersonNames) -> Self:
        """患者氏名を変更する。"""
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError("統合済みの患者の情報は変更できません。")
        return replace(self, names=names)

    def change_birth_date(self, birth_date: PatientBirthDate | None) -> Self:
        """患者の生年月日を変更する。Noneの場合は登録済みの生年月日を解除する。"""
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError("統合済みの患者の情報は変更できません。")
        return replace(self, birth_date=birth_date)

    def record_profile_change(self, change: PatientProfileChange) -> Self:
        """外部受付で受信したプロフィール差分を追記する。"""
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError(
                "統合済みの患者へ受信履歴は追加できません。"
            )
        if any(
            item.reception_id == change.reception_id
            and item.changed_fields == change.changed_fields
            and item.received_profile == change.received_profile
            for item in self.profile_history
        ):
            return self
        return replace(self, profile_history=(*self.profile_history, change))

    def deactivate(
        self,
        *,
        reason: PatientStatusReason,
        person_id: AccountPersonId,
        account_id: UserAccountId,
        recorded_at: datetime,
    ) -> Self:
        """患者を無効化（利用停止）する。"""
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError("統合済みの患者は無効化できません。")
        if self.status == PatientStatus.INACTIVE:
            return self
        change = PatientStatusChange(
            before=self.status,
            after=PatientStatus.INACTIVE,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
        return replace(
            self,
            status=PatientStatus.INACTIVE,
            status_history=(*self.status_history, change),
        )

    def reactivate(
        self,
        *,
        reason: PatientStatusReason,
        person_id: AccountPersonId,
        account_id: UserAccountId,
        recorded_at: datetime,
    ) -> Self:
        """患者を再有効化する。"""
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError("統合済みの患者は再有効化できません。")
        if self.status == PatientStatus.ACTIVE:
            return self
        change = PatientStatusChange(
            before=self.status,
            after=PatientStatus.ACTIVE,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
        return replace(
            self,
            status=PatientStatus.ACTIVE,
            status_history=(*self.status_history, change),
        )

    def merge_into(
        self,
        target_patient_id: PatientId,
        *,
        reason: PatientStatusReason,
        person_id: AccountPersonId,
        account_id: UserAccountId,
        recorded_at: datetime,
    ) -> Self:
        """別の患者集約へ統合する。"""
        if target_patient_id == self.id:
            raise PatientStateConflictError("自身へ統合することはできません。")
        if self.status == PatientStatus.MERGED:
            raise PatientStateConflictError(
                "既に統合済みの患者を再度統合することはできません。"
            )
        change = PatientStatusChange(
            before=self.status,
            after=PatientStatus.MERGED,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
            merged_into_id=target_patient_id,
        )
        return replace(
            self,
            status=PatientStatus.MERGED,
            merged_into_id=target_patient_id,
            status_history=(*self.status_history, change),
        )
