"""care_eventの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class EventTypeId(EntityUUID):
    """イベント種別の一意識別子。"""

    identifier_name = "イベント種別ID"


class EventId(EntityUUID):
    """業務イベントの一意識別子。"""

    identifier_name = "イベントID"
