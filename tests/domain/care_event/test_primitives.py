"""業務イベントが使うUUID識別子の契約。"""

from __future__ import annotations

from app.domain.care_event.primitives import EventId, EventTypeId


def test_tc45_10_Eventと種別IDは_UUIDv7で生成される() -> None:
    assert EventId.generate().value.version == 7
    assert EventTypeId.generate().value.version == 7
