"""イベント種別の名称競合を、作成と更新で共通に検証する。"""

from __future__ import annotations

from app.domain.care_event.entities import EventDefinition
from app.domain.care_event.primitives import EventTypeName
from app.domain.foundation.exceptions import DomainError


def ensure_event_definition_name_available(
    definitions: tuple[EventDefinition, ...], name: EventTypeName
) -> None:
    if any(
        item.corporate_id is not None and item.is_active and (item.name == name)
        for item in definitions
    ):
        raise DomainError("法人内で有効な同名イベント種別があります。")
