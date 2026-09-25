"""受付指紋と店舗別外部患者IDのPostgreSQL契約。"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.prescription.primitives import PrescriptionId
from app.domain.reception.primitives import (
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.reception.reception import Reception, ReceptionCorrection
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.infrastructure.postgres.schema import patient_external_identifiers, receptions
from tests.factories.persistence_factory import create_patient
from tests.factories.store_factory import create_store
from tests.integration.organization_helpers import setup_organization


def _identifier_row(
    *,
    row_id: uuid.UUID,
    corporate_id: uuid.UUID,
    patient_id: uuid.UUID,
    store_id: uuid.UUID | None,
    external_patient_id: str,
) -> dict[str, object]:
    """外部患者ID行をDB契約テスト用の列値へ展開する。"""
    now = datetime.now(UTC)
    return {
        "id": row_id,
        "corporate_id": corporate_id,
        "patient_id": patient_id,
        "system_name": "recept",
        "external_patient_id": external_patient_id,
        "store_id": store_id,
        "is_active": True,
        "payload": json.dumps(
            {
                "id": str(row_id),
                "corporate_id": str(corporate_id),
                "patient_id": str(patient_id),
                "system_name": "recept",
                "external_patient_id": external_patient_id,
                "store_id": str(store_id) if store_id is not None else None,
                "is_active": True,
            }
        ),
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_tc72_店舗スコープ外部IDのDB列一意性と未スコープ行を維持する(
    engine: AsyncEngine,
) -> None:
    """NULLの旧対応付けを残し、外部IDの有効一意性を店舗単位にする。"""
    assert patient_external_identifiers.c.get("store_id") is not None

    async with engine.connect() as connection:
        index_definition = await connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = 'uq_patient_external_identifiers_active_source'"
            )
        )
    assert isinstance(index_definition, str)
    assert "store_id" in index_definition

    corporate_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    store_a = uuid.uuid4()
    store_b = uuid.uuid4()
    legacy_row = _identifier_row(
        row_id=uuid.uuid4(),
        corporate_id=corporate_id,
        patient_id=patient_id,
        store_id=None,
        external_patient_id="SHARED-42",
    )
    store_a_row = _identifier_row(
        row_id=uuid.uuid4(),
        corporate_id=corporate_id,
        patient_id=patient_id,
        store_id=store_a,
        external_patient_id="SHARED-42",
    )
    store_b_row = _identifier_row(
        row_id=uuid.uuid4(),
        corporate_id=corporate_id,
        patient_id=patient_id,
        store_id=store_b,
        external_patient_id="SHARED-42",
    )

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO patient_external_identifiers "
                "(id, corporate_id, patient_id, system_name, external_patient_id, "
                "store_id, is_active, payload, version, created_at, updated_at) "
                "VALUES (:id, :corporate_id, :patient_id, :system_name, "
                ":external_patient_id, :store_id, :is_active, "
                "CAST(:payload AS jsonb), :version, :created_at, :updated_at)"
            ),
            [legacy_row, store_a_row, store_b_row],
        )

    duplicate_row = _identifier_row(
        row_id=uuid.uuid4(),
        corporate_id=corporate_id,
        patient_id=uuid.uuid4(),
        store_id=store_a,
        external_patient_id="SHARED-42",
    )
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO patient_external_identifiers "
                    "(id, corporate_id, patient_id, system_name, external_patient_id, "
                    "store_id, is_active, payload, version, created_at, updated_at) "
                    "VALUES (:id, :corporate_id, :patient_id, :system_name, "
                    ":external_patient_id, :store_id, :is_active, "
                    "CAST(:payload AS jsonb), :version, :created_at, :updated_at)"
                ),
                duplicate_row,
            )

    async with engine.connect() as connection:
        saved_rows = (
            await connection.execute(
                text(
                    "SELECT store_id FROM patient_external_identifiers "
                    "WHERE corporate_id = :corporate_id AND external_patient_id = :external_id"
                ),
                {"corporate_id": corporate_id, "external_id": "SHARED-42"},
            )
        ).all()
    assert len(saved_rows) == 3
    assert {row[0] for row in saved_rows} == {None, store_a, store_b}


@pytest.mark.asyncio
async def test_tc73_受付指紋と訂正関連IDはRepository再生成後も残る(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """受付IDの店舗スコープを保ちRepository再生成後に両受付を復元する。"""
    assert tuple(receptions.primary_key.columns.keys()) == (
        "corporate_id",
        "store_id",
        "id",
    )
    organization = await setup_organization(engine, session_factory)
    patient = create_patient(corporate_id=organization.corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).patient.save(patient)
        await work.commit()

    reception_id = ReceptionId.generate()
    recorded_at = datetime(2026, 9, 23, 1, 2, 3, tzinfo=UTC)
    reception = Reception(
        id=reception_id,
        corporate_id=organization.corporate.id,
        store_id=organization.store.id,
        patient_id=patient.id,
        prescription_id=PrescriptionId.generate(),
        dispensing_id=DispensingId.generate(),
        medication_history_id=MedicationHistoryRecordId.generate(),
        latest_fingerprint=ReceptionFingerprint("a" * 64),
        field_fingerprints=(
            (
                ReceptionFieldPath("prescription.document_number"),
                ReceptionFingerprint("b" * 64),
            ),
        ),
        correction_history=(
            ReceptionCorrection(
                fingerprint=ReceptionFingerprint("a" * 64),
                changed_fields=(ReceptionFieldPath("prescription.document_number"),),
                received_at=recorded_at,
            ),
        ),
    )
    other_store_id = StoreId.generate()
    other_store_reception = replace(
        reception,
        store_id=other_store_id,
        latest_fingerprint=ReceptionFingerprint("c" * 64),
        correction_history=(),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repository = getattr(PostgresRepositorySet.create(work), "reception", None)
        assert repository is not None
        await repository.save(reception)
        await repository.save(other_store_reception)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        repository = getattr(PostgresRepositorySet.create(work), "reception", None)
        assert repository is not None
        restored = await repository.get(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            reception_id=reception_id,
        )
        restored_other_store = await repository.get(
            corporate_id=organization.corporate.id,
            store_id=other_store_id,
            reception_id=reception_id,
        )

    assert restored is not None
    assert restored_other_store is not None
    assert restored.id == reception.id
    assert restored.patient_id == reception.patient_id
    assert restored.prescription_id == reception.prescription_id
    assert restored.dispensing_id == reception.dispensing_id
    assert restored.medication_history_id == reception.medication_history_id
    assert restored.latest_fingerprint == reception.latest_fingerprint
    assert restored.field_fingerprints == reception.field_fingerprints
    assert restored.correction_history == reception.correction_history
    assert restored_other_store.id == reception.id
    assert restored_other_store.store_id == other_store_id
    assert restored_other_store.latest_fingerprint == ReceptionFingerprint("c" * 64)
    assert restored_other_store.latest_fingerprint != restored.latest_fingerprint

    async with engine.connect() as connection:
        saved_count = await connection.scalar(
            text(
                "SELECT count(*) FROM receptions "
                "WHERE corporate_id = :corporate_id AND id = :reception_id"
            ),
            {
                "corporate_id": organization.corporate.id.value,
                "reception_id": reception_id.value,
            },
        )
    assert saved_count == 2


@pytest.mark.asyncio
async def test_tc79_受付監査resource_idは複合UnitOfWork識別子でなく受付ID(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """監査のresource_idはReception.id、店舗は別のscope列へ記録する。"""
    organization = await setup_organization(engine, session_factory)
    patient = create_patient(corporate_id=organization.corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).patient.save(patient)
        await work.commit()

    reception_id = ReceptionId.generate()
    reception = Reception(
        id=reception_id,
        corporate_id=organization.corporate.id,
        store_id=organization.store.id,
        patient_id=patient.id,
        latest_fingerprint=ReceptionFingerprint("d" * 64),
        field_fingerprints=(
            (
                ReceptionFieldPath("prescription.document_number"),
                ReceptionFingerprint("e" * 64),
            ),
        ),
    )
    other_store = create_store(
        corporate_id=organization.corporate.id,
        name="受付監査二号店",
        kana="ウケツケカンサニゴウテン",
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).store.save(other_store)
        await work.commit()
    other_store_reception = replace(
        reception,
        store_id=other_store.id,
        latest_fingerprint=ReceptionFingerprint("f" * 64),
    )

    for store_reception in (reception, other_store_reception):
        async with organization.root.request_scope(
            authorization=organization.authorization
        ) as scope:
            await scope.repositories.reception.save(store_reception)

    async with engine.connect() as connection:
        audits = (
            (
                await connection.execute(
                    text(
                        "SELECT resource_id, corporate_id, store_id "
                        "FROM operation_audits "
                        "WHERE operation = 'receptions.create' "
                        "AND corporate_id = :corporate_id ORDER BY store_id"
                    ),
                    {
                        "corporate_id": organization.corporate.id.value,
                    },
                )
            )
            .mappings()
            .all()
        )

    assert len(audits) == 2
    assert {row["store_id"]: row["resource_id"] for row in audits} == {
        organization.store.id.value: reception_id.value,
        other_store.id.value: reception_id.value,
    }
    assert {row["corporate_id"] for row in audits} == {organization.corporate.id.value}
