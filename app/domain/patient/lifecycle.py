"""患者のライフサイクル状態と変更記録。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.primitives import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId


class PatientStatus(StrEnum):
    """患者のライフサイクル状態。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MERGED = "merged"


class PatientStatusReason(BaseNormalizedString):
    """患者の状態変更または名寄せ統合の理由。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("患者状態変更理由は空にできません。")
        if len(self.value) > 200:
            raise DomainValidationError(
                "患者状態変更理由は200文字以内で指定してください。"
            )


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
