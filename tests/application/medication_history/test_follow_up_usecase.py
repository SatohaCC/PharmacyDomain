"""旧フォローアップ入口が使う共通のEvent起点薬歴契約を検証する。"""

from dataclasses import replace

import pytest

from app.application.common.exceptions import NotFoundError
from app.domain.care_event.primitives import (
    EventId,
    EventTypeId,
    EventTypeName,
    EventTypeStandardCode,
)
from tests.application.medication_history.helpers import (
    create_fixture,
    create_start_command,
)


async def test_tc45_38_処方受付以外のEventからも同じ下書きを起票できる() -> None:
    fixture = create_fixture()
    command = create_start_command(fixture)
    event_id = EventId.parse(command.event_id)
    event = fixture.event_repository.items[event_id]
    fixture.event_repository.items[event_id] = replace(
        event,
        event_type_id=EventTypeId.generate(),
        event_type_standard_code=EventTypeStandardCode("telephone_follow_up"),
        event_type_name=EventTypeName("電話フォローアップ"),
        prescription_id=None,
        dispensing_id=None,
        reception_id=None,
    )

    dto = await fixture.start.execute(
        replace(command, dispensing_id=None, reception_id=None)
    )

    saved = await fixture.record_repository.get_by_event(
        corporate_id=fixture.corporate_id,
        event_id=event_id,
    )
    assert saved is not None
    assert dto.event_id == str(event_id.value)
    assert saved.dispensing_id is None
    assert saved.prescription_id is None


async def test_tc45_38_参照元Eventが解決できないと薬歴を作らない() -> None:
    fixture = create_fixture()
    command = replace(
        create_start_command(fixture),
        event_id=str(EventId.generate().value),
    )

    with pytest.raises(NotFoundError):
        await fixture.start.execute(command)

    assert fixture.record_repository.items == {}
