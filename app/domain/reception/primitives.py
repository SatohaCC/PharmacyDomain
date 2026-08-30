"""Receptionコンテキストの識別子と監査プリミティブ。"""

from __future__ import annotations

from typing import ClassVar

from app.domain.foundation.primitives.primitives import (
    BaseAwareTimestamp,
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


class CoverageRecordedAt(BaseAwareTimestamp):
    """資格選択を記録したUTC時刻。"""

    timestamp_name: ClassVar[str] = "記録時刻"


class OperatorPrincipalId(BaseNormalizedString):
    """認証基盤が確定した記録者の主体ID。"""
