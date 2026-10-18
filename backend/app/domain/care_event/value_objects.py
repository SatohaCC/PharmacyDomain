"""care_eventの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.care_event.identifiers import EventId
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
    EventTypeName,
)
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class RelatedEventReference:
    """関連Event選択で公開してよい本文を含まないメタデータ。"""

    id: EventId
    store_id: StoreId
    event_type_name: EventTypeName
    occurred_at: EventOccurredTimestamp | None
    created_at: EventCreatedTimestamp
