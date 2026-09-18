"""店舗の状態と本人特定済みの状態変更記録。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.actor import AccountPersonId, UserAccountId


class StoreStatus(StrEnum):
    """店舗の業務受付状態。"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class StoreStatusReason(BaseNormalizedString):
    """店舗の状態を変更した理由。"""


@dataclass(frozen=True, kw_only=True)
class StoreStatusChange(ValueObject):
    """店舗の状態遷移とその操作者。"""

    before: StoreStatus
    after: StoreStatus
    reason: StoreStatusReason
    person_id: AccountPersonId
    account_id: UserAccountId
    recorded_at: datetime

    def validate(self) -> None:
        """記録日時にタイムゾーンを要求する。"""
        if self.recorded_at.utcoffset() is None:
            raise DomainValidationError("記録日時にはタイムゾーンが必要です。")


class StoreStateConflictError(DomainError):
    """店舗の現在状態と要求された業務が競合する。"""

    default_code = "STORE_STATE_CONFLICT"
