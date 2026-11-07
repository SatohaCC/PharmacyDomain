"""店舗業務Event一覧および標準コード受付起票のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.care_event.commands.create_event import CreateEventCommand
from app.application.care_event.queries.list_store_care_events import (
    ListStoreCareEventsUseCase,
)
from app.application.care_event.queries.models import ListStoreCareEventsQuery
from app.domain.care_event.entities import EventDefinition
from app.domain.care_event.identifiers import EventTypeId
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.care_event_list_store_events import (
    ListStoreCareEventsProjection,
)
from tests.application.care_event.helpers import create_fixture


async def test_店舗業務イベント一覧_自店舗イベントのみ取得し他店舗は除外する() -> None:
    """店舗に発生した業務Event一覧が取得でき、他店舗のEventは除外されること。"""
    fixture = create_fixture()
    store_a = fixture.store_id
    store_b = StoreId.generate()
    patient = fixture.patient_id
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)

    # store_a でイベント作成
    event_1 = await fixture.create_event.execute(
        CreateEventCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(store_a.value),
            patient_id=str(patient.value),
            event_type_id=str(fixture.event_type_id.value),
            occurred_at=now,
        )
    )

    query_use_case = ListStoreCareEventsUseCase(
        reader=ListStoreCareEventsProjection(fixture.event_repository),
        corporate_access=fixture.corporate_access,
        store_operations=fixture.store_operations,
    )

    events_a = await query_use_case.execute(
        ListStoreCareEventsQuery(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(store_a.value),
        )
    )
    assert len(events_a) == 1
    assert events_a[0].event_id == event_1.event_id

    # store_b では0件
    events_b = await query_use_case.execute(
        ListStoreCareEventsQuery(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(store_b.value),
        )
    )
    assert len(events_b) == 0


async def test_業務イベント起票_標準コードとエイリアス指定_定義を解決して起票できる() -> (
    None
):
    """標準コードやエイリアス（phone, walk_in等）を指定してEventが起票できること。"""
    fixture = create_fixture()
    now = datetime(2026, 11, 7, 11, 0, tzinfo=UTC)

    # 標準定義を追加登録
    phone_def = EventDefinition(
        id=EventTypeId.generate(),
        name=EventTypeName("電話フォローアップ"),
        standard_code=EventTypeStandardCode("telephone_follow_up"),
    )
    fixture.event_definition_repository.items[phone_def.id] = phone_def

    # エイリアス "phone" で起票
    event_dto = await fixture.create_event.execute(
        CreateEventCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            standard_code="phone",
            occurred_at=now,
        )
    )

    assert event_dto.event_type_id == str(phone_def.id.value)
    assert event_dto.event_type_name == "電話フォローアップ"
