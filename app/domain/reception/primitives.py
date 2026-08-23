"""Receptionコンテキストの識別子と監査プリミティブ。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.base import DomainPrimitive
from app.base.domain.primitives.primitives import (
    BaseDate,
    BaseNormalizedString,
    EntityUUID,
)


class CoverageSelectionRecordId(EntityUUID):
    """適用資格選択履歴の一意識別子。"""

    identifier_name = "適用資格選択履歴ID"


class SourceCoverageId(EntityUUID):
    """Receptionが保持する選択元患者資格ID。"""

    identifier_name = "選択元患者資格ID"


class CoverageAppliedOn(BaseDate):
    """受付で資格を適用する業務日。"""


class CoverageRecordedAt(DomainPrimitive[datetime]):
    """資格選択を記録したUTC時刻。"""

    def _normalize(self, value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise DomainValidationError("記録時刻は日時型で指定してください。")
        if value.tzinfo is None or value.utcoffset() is None:
            raise DomainValidationError(
                "記録時刻はタイムゾーン付きで指定してください。"
            )
        return value.astimezone(UTC)

    def validate(self) -> None:
        if not isinstance(self.value, datetime):
            raise DomainValidationError("記録時刻は日時型で指定してください。")


class OperatorPrincipalId(BaseNormalizedString):
    """認証基盤が確定した記録者の主体ID。"""
