"""患者の自由記載の頭書きを表す値。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseFreeText
from app.domain.foundation.value_object import ValueObject
from app.domain.shared.actor import AccountPersonId, UserAccountId


class PatientHeadingText(BaseFreeText):
    """患者の自由記載の頭書き本文。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("頭書き本文は空にできません。")
        if len(self.value) > 10_000:
            raise DomainValidationError("頭書きは10,000文字以内で指定してください。")


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
    recorded_at: datetime

    def _normalize_fields(self) -> None:
        if (
            isinstance(self.recorded_at, datetime)
            and self.recorded_at.utcoffset() is not None
        ):
            object.__setattr__(self, "recorded_at", self.recorded_at.astimezone(UTC))

    def validate(self) -> None:
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise DomainValidationError("頭書きの記録日時にはタイムゾーンが必要です。")
