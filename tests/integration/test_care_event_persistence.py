"""CareEventとEvent単位の薬歴一意性を実PostgreSQLで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.common.optional_conversion import unwrap
from app.domain.care_event.event import Event
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventCreatedTimestamp,
    EventOccurredTimestamp,
    EventTypeName,
)
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
)
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import ReceptionFingerprint, ReceptionId
from app.domain.reception.reception import Reception
from app.infrastructure.postgres import schema
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import create_record
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate


@pytest.mark.asyncio
async def test_tc45_04_05_07_種別の一意性履歴読取と法人別一覧(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """標準コードの一意性、無効化後の既存Event、法人別の一覧範囲を検証する。"""
    corporate_a = create_corporate("Event定義法人A")
    corporate_b = create_corporate("Event定義法人B")
    store_a = create_store(corporate_id=corporate_a.id)
    patient_a = create_patient(corporate_id=corporate_a.id)
    custom_a = EventDefinition.create_custom(
        corporate_id=corporate_a.id,
        name=EventTypeName("法人Aの相談"),
    )
    custom_b = EventDefinition.create_custom(
        corporate_id=corporate_b.id,
        name=EventTypeName("法人Bの相談"),
    )
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.corporate.save(corporate_a)
        await repositories.corporate.save(corporate_b)
        await repositories.store.save(store_a)
        await repositories.patient.save(patient_a)
        await repositories.event_definition.save(custom_a)
        await repositories.event_definition.save(custom_b)
        definitions_a = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate_a.id
        )
        standard = next(item for item in definitions_a if item.corporate_id is None)
        event = Event.create(
            event_type_id=custom_a.id,
            event_type_name=custom_a.name,
            event_definition_corporate_id=corporate_a.id,
            corporate_id=corporate_a.id,
            store_id=store_a.id,
            patient_id=patient_a.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repositories.event.save(event)
        record = replace(
            create_record(
                corporate_id=corporate_a.id,
                store_id=store_a.id,
                patient_id=patient_a.id,
                event_id=event.id,
            ),
            prescription_id=None,
            dispensing_id=None,
        )
        await repositories.medication_history.save(record)
        await repositories.event_definition.save(custom_a.deactivate())
        await work.commit()

    duplicate_id = uuid4()
    duplicate_standard_code = standard.standard_code
    assert duplicate_standard_code is not None
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.event_definitions).values(
                    id=duplicate_id,
                    corporate_id=None,
                    standard_code=duplicate_standard_code.value,
                    name="重複標準種別",
                    is_active=True,
                    payload={
                        "id": str(duplicate_id),
                        "corporate_id": None,
                        "standard_code": duplicate_standard_code.value,
                        "name": "重複標準種別",
                        "is_active": True,
                    },
                    version=1,
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
            )

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        definitions_a = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate_a.id
        )
        definitions_b = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate_b.id
        )
        stored_event = await repositories.event.get(
            corporate_id=corporate_a.id,
            event_id=event.id,
        )
        stored_record = await repositories.medication_history.get_by_event(
            corporate_id=corporate_a.id,
            event_id=event.id,
        )

    assert {item.name.value for item in definitions_a} == {
        item.name.value for item in definitions_a if item.corporate_id is None
    } | {"法人Aの相談"}
    assert {item.name.value for item in definitions_b} == {
        item.name.value for item in definitions_b if item.corporate_id is None
    } | {"法人Bの相談"}
    assert "法人Bの相談" not in {item.name.value for item in definitions_a}
    assert "法人Aの相談" not in {item.name.value for item in definitions_b}
    deactivated_custom = next(item for item in definitions_a if item.id == custom_a.id)
    assert not deactivated_custom.is_active
    assert stored_event is not None
    assert stored_event.event_type_name == EventTypeName("法人Aの相談")
    assert stored_record is not None
    assert stored_record.event_id == event.id


async def test_tc45_21_22_23_58_Eventと薬歴のPostgreSQL往復と一意性(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Event・定義・薬歴を復元し、同じEventへの二重記録をDBで拒否する。"""
    corporate = create_corporate("Event永続化テスト法人")
    store = create_store(corporate_id=corporate.id, name="Event永続化テスト店舗")
    patient = create_patient(corporate_id=corporate.id)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    writer = PostgresUnitOfWork(session_factory)
    async with writer:
        repositories = PostgresRepositorySet.create(writer)
        await repositories.corporate.save(corporate)
        await repositories.store.save(store)
        await repositories.patient.save(patient)

        definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        definition = next(
            item
            for item in definitions
            if item.corporate_id is None
            and item.standard_code is not None
            and item.standard_code.value == "in_person_consultation"
        )
        event = Event.create(
            event_type_id=definition.id,
            event_type_standard_code=definition.standard_code,
            event_type_name=definition.name,
            corporate_id=corporate.id,
            store_id=store.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repositories.event.save(event)

        record = replace(
            create_record(
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient.id,
                event_id=event.id,
            ),
            prescription_id=None,
            dispensing_id=None,
        )
        await repositories.medication_history.save(record)
        await writer.commit()

    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        repositories = PostgresRepositorySet.create(reader)
        restored_event = await repositories.event.get(
            corporate_id=corporate.id, event_id=event.id
        )
        restored_record = await repositories.medication_history.get_by_event(
            corporate_id=corporate.id, event_id=event.id
        )
        candidates = await repositories.event.list_related_candidates(
            corporate_id=corporate.id, patient_id=patient.id
        )

    assert restored_event is not None
    assert restored_event.event_type_standard_code == definition.standard_code
    assert restored_event.occurred_at == EventOccurredTimestamp(occurred_at)
    assert restored_record is not None
    assert restored_record.id == record.id
    assert restored_record.event_id == event.id
    assert [item.id for item in candidates] == [event.id]

    conflicting = PostgresUnitOfWork(session_factory)
    async with conflicting:
        repositories = PostgresRepositorySet.create(conflicting)
        with pytest.raises(MedicationHistoryAlreadyExistsError):
            await repositories.medication_history.save(
                replace(record, id=MedicationHistoryRecordId.generate())
            )


async def test_tc45_08_Event種別の不正参照やNULL迂回がDBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """標準・法人種別の整合性と、NULL列による存在確認迂回の拒否を実DBで検証する。"""
    corp_a = create_corporate("種別検証法人A")
    corp_b = create_corporate("種別検証法人B")
    store_a = create_store(corporate_id=corp_a.id, name="店舗A")
    patient_a = create_patient(corporate_id=corp_a.id)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    custom_b = EventDefinition.create_custom(
        corporate_id=corp_b.id,
        name=EventTypeName("法人B独自種別"),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp_a)
        await repos.corporate.save(corp_b)
        await repos.store.save(store_a)
        await repos.patient.save(patient_a)
        await repos.event_definition.save(custom_b)
        await work.commit()

    # 1. 存在しないevent_type_idでevent_definition_corporate_id=None（MATCH SIMPLE迂回試行） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=uuid4(),
                    event_definition_corporate_id=None,
                    event_type_standard_code="fake_code",
                    event_type_name="架空種別",
                    corporate_id=corp_a.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 2. 別法人Bの独自種別IDでevent_definition_corporate_id=None（標準偽装） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=custom_b.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=None,
                    event_type_name="法人B独自種別の偽装",
                    corporate_id=corp_a.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 3. 別法人Bの独自種別IDでevent_definition_corporate_id=corp_a.id（法人一致偽装） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=custom_b.id.value,
                    event_definition_corporate_id=corp_a.id.value,
                    event_type_standard_code=None,
                    event_type_name="法人B独自種別の偽装2",
                    corporate_id=corp_a.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )


async def test_tc45_16_Event関連参照の法人患者不一致や自己参照がDBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """関連元Eventの法人・患者境界と非自己参照を実DBで検証する。"""
    corp_a = create_corporate("関連検証法人A")
    corp_b = create_corporate("関連検証法人B")
    store_a = create_store(corporate_id=corp_a.id, name="店舗A")
    store_b = create_store(corporate_id=corp_b.id, name="店舗B")
    patient_a1 = create_patient(corporate_id=corp_a.id, patient_number=1)
    patient_a2 = create_patient(corporate_id=corp_a.id, patient_number=2)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp_a)
        await repos.corporate.save(corp_b)
        await repos.store.save(store_a)
        await repos.store.save(store_b)
        await repos.patient.save(patient_a1)
        await repos.patient.save(patient_a2)
        definitions = await repos.event_definition.list_for_corporate(
            corporate_id=corp_a.id
        )
        def_std = definitions[0]
        base_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp_a.id,
            store_id=store_a.id,
            patient_id=patient_a1.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repos.event.save(base_event)
        alternate_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp_a.id,
            store_id=store_a.id,
            patient_id=patient_a1.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        linked_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp_a.id,
            store_id=store_a.id,
            patient_id=patient_a1.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
            related_event_id=base_event.id,
        )
        await repos.event.save(alternate_event)
        await repos.event.save(linked_event)
        await work.commit()

    # 1. 別法人Bを指定して法人Aのbase_eventを関連元にする -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp_b.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a1.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    related_event_id=base_event.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 4. 作成後の関連元付け替え -> 拒否 (既存行の更新で循環も作れない)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.care_events)
                .where(schema.care_events.c.id == linked_event.id.value)
                .values(related_event_id=alternate_event.id.value)
            )

    # 5. 作成後の法人・店舗・患者の変更 -> 拒否
    for changed_scope in (
        {"corporate_id": corp_b.id.value},
        {"store_id": store_b.id.value},
        {"patient_id": patient_a2.id.value},
    ):
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(schema.care_events)
                    .where(schema.care_events.c.id == linked_event.id.value)
                    .values(**changed_scope)
                )

    # 2. 別患者A2を指定して患者A1のbase_eventを関連元にする -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp_a.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a2.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    related_event_id=base_event.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 3. 自己参照 (related_event_id == id) -> 拒否
    self_id = uuid4()
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=self_id,
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp_a.id.value,
                    store_id=store_a.id.value,
                    patient_id=patient_a1.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    related_event_id=self_id,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )


async def test_tc45_18_Eventの受付処方調剤の不整合がDBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Eventの受付・処方箋・調剤参照のスコープ一致と調剤の処方箋必須制約を検証する。"""
    corp = create_corporate("リソース検証法人")
    store1 = create_store(corporate_id=corp.id, name="店舗1")
    store2 = create_store(corporate_id=corp.id, name="店舗2")
    patient1 = create_patient(corporate_id=corp.id, patient_number=1)
    patient2 = create_patient(corporate_id=corp.id, patient_number=2)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    prescription1 = create_prescription(
        corporate_id=corp.id, store_id=store1.id, patient_id=patient1.id
    )
    dispensing1 = create_dispensing(
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=patient1.id,
        prescription_id=prescription1.id,
    )
    reception1 = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=patient1.id,
        latest_fingerprint=ReceptionFingerprint("b" * 64),
        field_fingerprints=(),
        prescription_id=prescription1.id,
        dispensing_id=dispensing1.id,
    )
    reception_without_resources = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=patient1.id,
        latest_fingerprint=ReceptionFingerprint("c" * 64),
        field_fingerprints=(),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp)
        await repos.store.save(store1)
        await repos.store.save(store2)
        await repos.patient.save(patient1)
        await repos.patient.save(patient2)
        await repos.prescription.save(prescription1)
        await repos.dispensing.save(dispensing1)
        await repos.reception.save(reception1)
        await repos.reception.save(reception_without_resources)
        definitions = await repos.event_definition.list_for_corporate(
            corporate_id=corp.id
        )
        def_std = definitions[0]
        await work.commit()

    # 1. 処方箋の患者不一致（patient2のEventにprescription1を指定） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp.id.value,
                    store_id=store1.id.value,
                    patient_id=patient2.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    prescription_id=prescription1.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 4. 受付の処方・調剤をEvent側で省略 -> 拒否 (care_events_reception_resources_guard)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp.id.value,
                    store_id=store1.id.value,
                    patient_id=patient1.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    reception_id=reception1.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 5. 受付とEventの患者不一致（双方の法人・店舗・受付IDは一致） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp.id.value,
                    store_id=store1.id.value,
                    patient_id=patient2.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    reception_id=reception_without_resources.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 2. 調剤があるのに処方箋がない (dispensing_id IS NOT NULL, prescription_id IS NULL) -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp.id.value,
                    store_id=store1.id.value,
                    patient_id=patient1.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    dispensing_id=dispensing1.id.value,
                    prescription_id=None,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )

    # 3. 受付の店舗不一致（store2のEventにstore1のreception1を指定） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.care_events).values(
                    id=uuid4(),
                    event_type_id=def_std.id.value,
                    event_definition_corporate_id=None,
                    event_type_standard_code=unwrap(def_std.standard_code),
                    event_type_name=def_std.name.value,
                    corporate_id=corp.id.value,
                    store_id=store2.id.value,
                    patient_id=patient1.id.value,
                    occurred_at=occurred_at,
                    occurred_at_is_unknown=False,
                    created_at=occurred_at,
                    reception_id=reception1.id.value,
                    payload={},
                    version=1,
                    updated_at=occurred_at,
                )
            )


async def test_tc45_23_薬歴とEventの処方調剤不一致直接INSERTがDBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """薬歴とEventの処方箋・調剤ID写しの一致をトリガで保証し、不一致直接INSERTを拒否する。"""
    corp = create_corporate("薬歴写し検証法人")
    foreign_corp = create_corporate("薬歴写し別法人")
    store = create_store(corporate_id=corp.id, name="店舗")
    other_store = create_store(corporate_id=corp.id, name="別店舗")
    foreign_store = create_store(corporate_id=foreign_corp.id, name="別法人店舗")
    patient = create_patient(corporate_id=corp.id)
    other_patient = create_patient(corporate_id=corp.id, patient_number=2)
    foreign_patient = create_patient(corporate_id=foreign_corp.id)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    pres1 = create_prescription(
        corporate_id=corp.id, store_id=store.id, patient_id=patient.id
    )
    pres2 = create_prescription(
        corporate_id=corp.id, store_id=store.id, patient_id=patient.id
    )
    disp1 = create_dispensing(
        corporate_id=corp.id,
        store_id=store.id,
        patient_id=patient.id,
        prescription_id=pres1.id,
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp)
        await repos.corporate.save(foreign_corp)
        await repos.store.save(store)
        await repos.store.save(other_store)
        await repos.store.save(foreign_store)
        await repos.patient.save(patient)
        await repos.patient.save(other_patient)
        await repos.patient.save(foreign_patient)
        await repos.prescription.save(pres1)
        await repos.prescription.save(pres2)
        await repos.dispensing.save(disp1)
        definitions = await repos.event_definition.list_for_corporate(
            corporate_id=corp.id
        )
        def_std = definitions[0]

        event_with_both = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp.id,
            store_id=store.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
            prescription_id=pres1.id,
            dispensing_id=disp1.id,
        )
        event_with_none = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp.id,
            store_id=store.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repos.event.save(event_with_both)
        await repos.event.save(event_with_none)
        await work.commit()

    # 1. Eventがpres1を持つとき、薬歴側でpres2を指定（処方箋不一致直接INSERT） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.medication_history_records).values(
                    id=uuid4(),
                    corporate_id=corp.id.value,
                    store_id=store.id.value,
                    patient_id=patient.id.value,
                    event_id=event_with_both.id.value,
                    prescription_id=pres2.id.value,
                    dispensing_id=disp1.id.value,
                    status="draft",
                    payload={"status": "draft"},
                    version=1,
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
            )

    # 2. Eventがpres1を持つとき、薬歴側でprescription_id=None（処方箋省略直接INSERT） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.medication_history_records).values(
                    id=uuid4(),
                    corporate_id=corp.id.value,
                    store_id=store.id.value,
                    patient_id=patient.id.value,
                    event_id=event_with_both.id.value,
                    prescription_id=None,
                    dispensing_id=None,
                    status="draft",
                    payload={"status": "draft"},
                    version=1,
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
            )

    # 3. Eventが調剤を持たないとき、薬歴側でpres1を指定（処方箋付加直接INSERT） -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                insert(schema.medication_history_records).values(
                    id=uuid4(),
                    corporate_id=corp.id.value,
                    store_id=store.id.value,
                    patient_id=patient.id.value,
                    event_id=event_with_none.id.value,
                    prescription_id=pres1.id.value,
                    dispensing_id=None,
                    status="draft",
                    payload={"status": "draft"},
                    version=1,
                    created_at=occurred_at,
                    updated_at=occurred_at,
                )
            )

    # 4. Eventの法人・店舗・患者スコープを薬歴側で差し替える -> 拒否
    for changed_scope in (
        {
            "corporate_id": foreign_corp.id.value,
            "store_id": foreign_store.id.value,
            "patient_id": foreign_patient.id.value,
        },
        {"store_id": other_store.id.value},
        {"patient_id": other_patient.id.value},
    ):
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    insert(schema.medication_history_records).values(
                        id=uuid4(),
                        corporate_id=changed_scope.get("corporate_id", corp.id.value),
                        store_id=changed_scope.get("store_id", store.id.value),
                        patient_id=changed_scope.get("patient_id", patient.id.value),
                        event_id=event_with_both.id.value,
                        prescription_id=pres1.id.value,
                        dispensing_id=disp1.id.value,
                        status="draft",
                        payload={"status": "draft"},
                        version=1,
                        created_at=occurred_at,
                        updated_at=occurred_at,
                    )
                )

    # 5. 完全に一致する直接INSERT -> 成立
    async with session_factory() as session:
        await session.execute(
            insert(schema.medication_history_records).values(
                id=uuid4(),
                corporate_id=corp.id.value,
                store_id=store.id.value,
                patient_id=patient.id.value,
                event_id=event_with_both.id.value,
                prescription_id=pres1.id.value,
                dispensing_id=disp1.id.value,
                status="draft",
                payload={"status": "draft"},
                version=1,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        await session.commit()


async def test_tc45_39_ReceptionのEvent参照不整合や二重関連がDBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ReceptionのEvent参照が店舗・受付IDの複合FKで保護され、一意であることを実DBで検証する。"""
    corp = create_corporate("受付Event逆方向FK検証法人")
    store1 = create_store(corporate_id=corp.id, name="店舗1")
    store2 = create_store(corporate_id=corp.id, name="店舗2")
    patient = create_patient(corporate_id=corp.id)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    rec1 = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=patient.id,
        latest_fingerprint=ReceptionFingerprint("c" * 64),
        field_fingerprints=(),
    )
    rec2 = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=patient.id,
        latest_fingerprint=ReceptionFingerprint("d" * 64),
        field_fingerprints=(),
    )
    rec_patient_mismatch = Reception(
        id=ReceptionId.generate(),
        corporate_id=corp.id,
        store_id=store1.id,
        patient_id=PatientId.generate(),
        latest_fingerprint=ReceptionFingerprint("e" * 64),
        field_fingerprints=(),
    )

    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        await repos.corporate.save(corp)
        await repos.store.save(store1)
        await repos.store.save(store2)
        await repos.patient.save(patient)
        await repos.reception.save(rec1)
        await repos.reception.save(rec2)
        await repos.reception.save(rec_patient_mismatch)
        definitions = await repos.event_definition.list_for_corporate(
            corporate_id=corp.id
        )
        def_std = definitions[0]

        valid_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp.id,
            store_id=store1.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
            reception_id=rec1.id,
        )
        store2_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp.id,
            store_id=store2.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        no_rec_event = Event.create(
            event_type_id=def_std.id,
            event_type_standard_code=def_std.standard_code,
            event_type_name=def_std.name,
            corporate_id=corp.id,
            store_id=store1.id,
            patient_id=patient.id,
            occurred_at=EventOccurredTimestamp(occurred_at),
            created_at=EventCreatedTimestamp(occurred_at),
        )
        await repos.event.save(valid_event)
        await repos.event.save(store2_event)
        await repos.event.save(no_rec_event)
        await work.commit()

    # 1. 別店舗store2のEventをrec1のevent_idに指定 -> 拒否 (fk_receptions_event_scope)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.receptions)
                .where(schema.receptions.c.id == rec1.id.value)
                .values(event_id=store2_event.id.value)
            )

    # 5. Eventの患者と受付payloadの患者が異なる関連付け -> 拒否
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.receptions)
                .where(schema.receptions.c.id == rec_patient_mismatch.id.value)
                .values(event_id=valid_event.id.value)
            )

    # 2. reception_idがNoneのEventをrec1のevent_idに指定 -> 拒否 (fk_receptions_event_scope)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.receptions)
                .where(schema.receptions.c.id == rec1.id.value)
                .values(event_id=no_rec_event.id.value)
            )

    # 3. 正しいvalid_eventへの更新 -> 成立
    async with session_factory() as session:
        await session.execute(
            update(schema.receptions)
            .where(schema.receptions.c.id == rec1.id.value)
            .values(event_id=valid_event.id.value)
        )
        await session.commit()

    # 3b. 関連付け後にReception payloadの患者を変更 -> 拒否 (receptions_event_resources_guard)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.receptions)
                .where(schema.receptions.c.id == rec1.id.value)
                .values(payload={"patient_id": str(PatientId.generate())})
            )

    # 4. 別の受付rec2に同じvalid_eventを指定（二重関連） -> 拒否 (uq_receptions_event)
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(schema.receptions)
                .where(schema.receptions.c.id == rec2.id.value)
                .values(event_id=valid_event.id.value)
            )


async def test_tc45_全種別のEvent作成と薬歴保存の成立(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """全6つの標準種別と法人独自種別でEventおよび薬歴が正常に往復できる。"""
    corporate = create_corporate("全種別横断テスト法人")
    store = create_store(corporate_id=corporate.id, name="全種別店舗")
    patient = create_patient(corporate_id=corporate.id)
    occurred_at = datetime(2026, 9, 26, 3, 0, tzinfo=UTC)

    custom = EventDefinition.create_custom(
        corporate_id=corporate.id,
        name=EventTypeName("特別相談"),
    )

    writer = PostgresUnitOfWork(session_factory)
    async with writer:
        repositories = PostgresRepositorySet.create(writer)
        await repositories.corporate.save(corporate)
        await repositories.store.save(store)
        await repositories.patient.save(patient)
        await repositories.event_definition.save(custom)

        all_definitions = await repositories.event_definition.list_for_corporate(
            corporate_id=corporate.id
        )
        assert len(all_definitions) == 7  # 6 standard + 1 custom

        for definition in all_definitions:
            event = Event.create(
                event_type_id=definition.id,
                event_definition_corporate_id=definition.corporate_id,
                event_type_standard_code=definition.standard_code,
                event_type_name=definition.name,
                corporate_id=corporate.id,
                store_id=store.id,
                patient_id=patient.id,
                occurred_at=EventOccurredTimestamp(occurred_at),
                created_at=EventCreatedTimestamp(occurred_at),
            )
            await repositories.event.save(event)

            record = replace(
                create_record(
                    corporate_id=corporate.id,
                    store_id=store.id,
                    patient_id=patient.id,
                    event_id=event.id,
                ),
                prescription_id=None,
                dispensing_id=None,
            )
            await repositories.medication_history.save(record)

        await writer.commit()

    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        repositories = PostgresRepositorySet.create(reader)
        candidates = await repositories.event.list_related_candidates(
            corporate_id=corporate.id, patient_id=patient.id
        )
        assert len(candidates) == 7
        for definition in all_definitions:
            matching_candidate = next(
                c for c in candidates if c.event_type_name == definition.name
            )
            found_record = await repositories.medication_history.get_by_event(
                corporate_id=corporate.id, event_id=matching_candidate.id
            )
            assert found_record is not None
