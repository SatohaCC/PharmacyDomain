"""NSIPS受付取込の全集約書込みを実PostgreSQLの一トランザクションで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, ClassVar

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.integration.nsips.ingest_nsips import IngestNsipsCommand
from app.application.integration.nsips.models import (
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId, DispensingProcessStatus
from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    FinalizedTimestamp,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.value_objects import ExternalCorrectionKind
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import ExternalPatientId, PatientAddress
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
from app.domain.prescription.primitives import (
    PrescriptionId,
    PrescriptionStatus,
)
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.reception import Reception
from app.domain.reception.repository import ReceptionRepository
from app.domain.shared.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
)
from app.domain.store.primitives import StoreId
from app.infrastructure.postgres.codec import decode_aggregate
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from tests.factories.medication_history_factory import (
    create_record,
    finalize_record_with_review,
)
from tests.factories.medicine_catalog_factory import create_medicine
from tests.factories.persistence_factory import create_patient
from tests.integration.medication_history_helpers import save_history_with_event
from tests.integration.organization_helpers import appoint_manager, setup_organization

_EXPECTED_INGEST_ROW_COUNTS: dict[str, int] = {
    "patients": 1,
    "patient_external_identifiers": 1,
    "patient_coverages": 1,
    "coverage_selection_records": 1,
    "receptions": 1,
    "prescriptions": 1,
    "dispensing_processes": 1,
    "care_events": 0,
    "medication_history_records": 0,
}


class _LateIngestionFailure(RuntimeError):
    """受付のハッシュ値を保存した直後に注入するテスト用の後段障害。"""


class _FailAfterReceptionSave:
    """受付保存後に同じUoW内の全行を確認して失敗する。"""

    _delegate: ReceptionRepository
    _session: AsyncSession
    _corporate_id: CorporateId
    observed_patient_kanji_name: str | None
    expected_row_counts: ClassVar[dict[str, int]] = _EXPECTED_INGEST_ROW_COUNTS

    def __init__(
        self,
        delegate: ReceptionRepository,
        session: AsyncSession,
        corporate_id: CorporateId,
    ) -> None:
        self._delegate = delegate
        self._session = session
        self._corporate_id = corporate_id
        self.observed_patient_kanji_name = None

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: ReceptionId,
    ) -> Reception | None:
        """実Repositoryの境界検索をそのまま委譲する。"""
        return await self._delegate.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )

    async def save(self, reception: Reception) -> None:
        """受付保存後に各テーブルを確認し、UoWへ失敗を返す。"""
        await self._delegate.save(reception)
        for table, expected_count in self.expected_row_counts.items():
            count = await self._session.scalar(
                text(
                    f"SELECT count(*) FROM {table} WHERE corporate_id = :corporate_id"
                ),
                {"corporate_id": self._corporate_id.value},
            )
            assert count == expected_count, (
                f"失敗注入前の {table} の件数が期待値と異なる。"
            )
        patient_payload = await self._session.scalar(
            text("SELECT payload FROM patients WHERE id = :patient_id"),
            {"patient_id": reception.patient_id.value},
        )
        reception_payload = await self._session.scalar(
            text(
                "SELECT payload FROM receptions "
                "WHERE corporate_id = :corporate_id AND store_id = :store_id "
                "AND id = :reception_id"
            ),
            {
                "corporate_id": reception.corporate_id.value,
                "store_id": reception.store_id.value,
                "reception_id": reception.id.value,
            },
        )
        assert isinstance(patient_payload, dict)
        assert patient_payload["profile_history"]
        persisted_patient = decode_aggregate(patient_payload, Patient)
        self.observed_patient_kanji_name = persisted_patient.names.kanji.full_name
        assert isinstance(reception_payload, dict)
        assert reception_payload["correction_history"]
        raise _LateIngestionFailure("受付保存後の障害を注入した。")


class _FailAfterHistorySave:
    """薬歴保存後に障害を注入して後続処理またはトランザクションを失敗させる。"""

    def __init__(
        self,
        delegate: MedicationHistoryRepository,
    ) -> None:
        self._delegate = delegate
        self.saved_calls = 0

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        return await self._delegate.get(corporate_id=corporate_id, record_id=record_id)

    async def save(self, record: MedicationHistoryRecord) -> None:
        await self._delegate.save(record)
        self.saved_calls += 1
        raise _LateIngestionFailure("薬歴保存直後の障害を注入した。")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _bundle() -> NsipsBundle:
    """実UoWで患者・資格・処方・調剤を取り込む構造化入力を返す。"""
    return NsipsBundle(
        header_version="structured-test",
        patient=NsipsPatientInfo(
            external_patient_id="NSIPS-TC44-PATIENT",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="NSIPS-TC44-DOCUMENT",
            issued_date=date(2026, 9, 17),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日1回食後",
                    dispensing_quantity=7,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="試験用医薬品",
                            dosage=Decimal("1"),
                            unit="錠",
                        ),
                    ),
                ),
            ),
        ),
        dispensed_date=date(2026, 9, 17),
        insurance=NsipsInsuranceInfo(
            insurer_number="12345678",
            insured_symbol="TC44-SYMBOL",
            insured_number="TC44-NUMBER",
            insured_type="self",
            benefit_ratio=70,
        ),
    )


@pytest.mark.asyncio
async def test_tc74_受付保存後の失敗で取込と変更履歴を一括rollbackする(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NSIPS取込は薬歴を作らず、患者・受付の更新を同じUoWでrollbackする。"""
    organization = await setup_organization(engine, session_factory)
    await appoint_manager(session_factory, organization)

    medicine = create_medicine(code="2171022F1029", name="試験用医薬品")
    medicine = replace(
        medicine,
        identifier=MedicineIdentifier(
            code_type=MedicineCodeType.RECEIPT,
            code=MedicineCode("610406001"),
        ),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).medicine_catalog.save(medicine)
        await work.commit()

    command = IngestNsipsCommand(
        corporate_id=str(organization.corporate.id.value),
        store_id=str(organization.store.id.value),
        dispenser_staff_id=str(organization.staff[0].id.value),
        reception_id=str(ReceptionId.generate().value),
        structured_bundle=_bundle(),
    )
    reception_id = command.reception_id
    assert reception_id is not None

    async with organization.root.request_scope(
        authorization=organization.authorization
    ) as scope:
        await scope.use_cases.integration.ingest_nsips.execute(command)

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        original_reception = await repositories.reception.get(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            reception_id=ReceptionId.parse(reception_id),
        )
        assert original_reception is not None
        original_patient = await repositories.patient.get(
            corporate_id=organization.corporate.id,
            patient_id=original_reception.patient_id,
        )
        assert original_patient is not None
        assert original_patient.profile_history == ()
        assert original_reception.correction_history == ()

    original_bundle = command.structured_bundle
    assert original_bundle is not None
    changed_bundle = replace(
        original_bundle,
        patient=replace(original_bundle.patient, kanji_name="山田花子"),
        prescription=replace(
            original_bundle.prescription, doctor_name="変更後の処方医"
        ),
    )
    changed_command = replace(command, structured_bundle=changed_bundle)
    fail_after_save: _FailAfterReceptionSave | None = None
    with pytest.raises(_LateIngestionFailure):
        async with organization.root.request_scope(
            authorization=organization.authorization
        ) as scope:
            use_case = scope.use_cases.integration.ingest_nsips
            original = use_case._reception_repo
            assert original is not None
            fail_after_save = _FailAfterReceptionSave(
                original,
                scope._unit_of_work.session,
                organization.corporate.id,
            )
            monkeypatch.setattr(
                use_case,
                "_reception_repo",
                fail_after_save,
            )
            await use_case.execute(changed_command)
    assert fail_after_save is not None
    assert fail_after_save.observed_patient_kanji_name == "山田 花子"

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        restored_reception = await repositories.reception.get(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            reception_id=ReceptionId.parse(reception_id),
        )
        assert restored_reception is not None
        assert restored_reception == original_reception
        restored_patient = await repositories.patient.get(
            corporate_id=organization.corporate.id,
            patient_id=original_patient.id,
        )
        assert restored_patient is not None
        assert restored_patient == original_patient
        assert restored_patient.profile_history == ()
        assert restored_patient.names == original_patient.names
        assert restored_reception.correction_history == ()
        assert restored_reception.latest_fingerprint == (
            original_reception.latest_fingerprint
        )

    async with engine.connect() as connection:
        counts = {
            table: (
                await connection.execute(
                    text(
                        f"SELECT count(*) FROM {table} "
                        "WHERE corporate_id = :corporate_id"
                    ),
                    {"corporate_id": organization.corporate.id.value},
                )
            ).scalar_one()
            for table in _EXPECTED_INGEST_ROW_COUNTS
        }
    assert counts == _EXPECTED_INGEST_ROW_COUNTS


@pytest.mark.asyncio
async def test_tc85_同一Patientの競合更新は古いversionを拒否し再試行履歴を保つ(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """先に確定したプロフィールを保ち、再読込後の更新履歴も追記する。"""
    organization = await setup_organization(engine, session_factory)
    patient = create_patient(corporate_id=organization.corporate.id)
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).patient.save(patient)
        await work.commit()

    first_reception = ReceptionId.generate()
    second_reception = ReceptionId.generate()
    recorded_at = datetime(2026, 9, 24, 1, 2, 3, tzinfo=UTC)

    def _change(reception_id: ReceptionId, address: str) -> PatientProfileChange:
        return PatientProfileChange(
            reception_id=reception_id,
            store_id=organization.store.id,
            external_patient_id=ExternalPatientId("POS-TC85"),
            recorded_at=recorded_at,
            changed_fields=("patient.address",),
            received_profile=PatientProfileSnapshot(
                names=patient.names,
                birth_date=patient.birth_date,
                gender=patient.gender,
                postal_code=patient.postal_code,
                address=PatientAddress(address),
                phone_number=patient.phone_number,
            ),
        )

    first_change = _change(first_reception, "東京都千代田区一丁目")
    second_change = _change(second_reception, "東京都中央区二丁目")
    async with (
        PostgresUnitOfWork(session_factory) as first_work,
        PostgresUnitOfWork(session_factory) as stale_work,
    ):
        first_repositories = PostgresRepositorySet.create(first_work)
        stale_repositories = PostgresRepositorySet.create(stale_work)
        first_read = await first_repositories.patient.get(
            corporate_id=organization.corporate.id,
            patient_id=patient.id,
        )
        stale_read = await stale_repositories.patient.get(
            corporate_id=organization.corporate.id,
            patient_id=patient.id,
        )
        assert first_read is not None
        assert stale_read is not None
        first_update = replace(
            first_read.record_profile_change(first_change),
            address=PatientAddress("東京都千代田区一丁目"),
        )
        stale_update = replace(
            stale_read.record_profile_change(second_change),
            address=PatientAddress("東京都中央区二丁目"),
        )
        await first_repositories.patient.save(first_update)
        await first_work.commit()
        with pytest.raises(ConcurrentModificationError):
            await stale_repositories.patient.save(stale_update)
        await stale_work.rollback()

    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        current = await repositories.patient.get(
            corporate_id=organization.corporate.id,
            patient_id=patient.id,
        )
        assert current is not None
        assert current.address == PatientAddress("東京都千代田区一丁目")
        assert len(current.profile_history) == 1
        retry = replace(
            current.record_profile_change(second_change),
            address=PatientAddress("東京都中央区二丁目"),
        )
        await repositories.patient.save(retry)
        await work.commit()

    async with PostgresUnitOfWork(session_factory) as work:
        final = await PostgresRepositorySet.create(work).patient.get(
            corporate_id=organization.corporate.id,
            patient_id=patient.id,
        )
        assert final is not None
        assert final.address == PatientAddress("東京都中央区二丁目")
        assert [item.reception_id for item in final.profile_history] == [
            first_reception,
            second_reception,
        ]


@pytest.mark.asyncio
async def test_TC36_削除通知処理中の失敗で処方と調剤と薬歴を一括rollbackする(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-file削除処理で一部が失敗した場合、Prescription/Dispensing/薬歴の全更新をrollbackする。"""
    organization = await setup_organization(engine, session_factory)
    await appoint_manager(session_factory, organization)

    medicine = create_medicine(code="2171022F1029", name="試験用医薬品")
    medicine = replace(
        medicine,
        identifier=MedicineIdentifier(
            code_type=MedicineCodeType.RECEIPT,
            code=MedicineCode("610406001"),
        ),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        await PostgresRepositorySet.create(work).medicine_catalog.save(medicine)
        await work.commit()

    reception_id_value = str(ReceptionId.generate().value)
    command = IngestNsipsCommand(
        corporate_id=str(organization.corporate.id.value),
        store_id=str(organization.store.id.value),
        dispenser_staff_id=str(organization.staff[0].id.value),
        reception_id=reception_id_value,
        structured_bundle=_bundle(),
    )

    async with organization.root.request_scope(
        authorization=organization.authorization
    ) as scope:
        res = await scope.use_cases.integration.ingest_nsips.execute(command)

    assert res.prescription_id is not None
    assert res.dispensing_id is not None
    prescription_id = PrescriptionId.parse(res.prescription_id)
    dispensing_id = DispensingId.parse(res.dispensing_id)

    # 薬歴を作成して確定し、受付に紐付ける
    history_id = MedicationHistoryRecordId.generate()
    now = datetime.now(UTC)
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        reception = await repos.reception.get(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            reception_id=ReceptionId.parse(reception_id_value),
        )
        assert reception is not None
        draft = create_record(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            patient_id=reception.patient_id,
            counselor_id=organization.staff[0].id,
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            counseled_at=now,
        )
        history_id = draft.id
        finalized = finalize_record_with_review(
            draft,
            finalized_at=FinalizedTimestamp(now),
            finalized_by=organization.staff[0].id,
        )
        await save_history_with_event(repos, finalized)
        await repos.reception.save(replace(reception, medication_history_id=history_id))
        await work.commit()

    original_bundle = command.structured_bundle
    assert original_bundle is not None
    delete_bundle = replace(
        original_bundle,
        correction_kind=ExternalCorrectionKind.DELETE,
    )
    delete_command = replace(command, structured_bundle=delete_bundle)

    fail_after_save: _FailAfterHistorySave | None = None
    with pytest.raises(_LateIngestionFailure):
        async with organization.root.request_scope(
            authorization=organization.authorization
        ) as scope:
            use_case = scope.use_cases.integration.ingest_nsips
            original_history_repo = use_case._medication_history_repo
            assert original_history_repo is not None
            fail_after_save = _FailAfterHistorySave(original_history_repo)
            monkeypatch.setattr(
                use_case,
                "_medication_history_repo",
                fail_after_save,
            )
            await use_case.execute(delete_command)

    assert fail_after_save is not None
    assert fail_after_save.saved_calls == 1

    # 検証: ロールバックされ、通知前の状態に戻っていること
    async with PostgresUnitOfWork(session_factory) as work:
        repos = PostgresRepositorySet.create(work)
        reloaded_rx = await repos.prescription.get(
            corporate_id=organization.corporate.id,
            prescription_id=prescription_id,
        )
        assert reloaded_rx is not None
        assert reloaded_rx.status is not PrescriptionStatus.CANCELLED

        reloaded_dispensing = await repos.dispensing.get(
            corporate_id=organization.corporate.id,
            dispensing_id=dispensing_id,
        )
        assert reloaded_dispensing is not None
        assert reloaded_dispensing.status is not DispensingProcessStatus.CANCELLED

        reloaded_history = await repos.medication_history.get(
            corporate_id=organization.corporate.id,
            record_id=history_id,
        )
        assert reloaded_history is not None
        assert reloaded_history.external_corrections == ()
        assert reloaded_history.has_pending_correction_review is False

        reloaded_reception = await repos.reception.get(
            corporate_id=organization.corporate.id,
            store_id=organization.store.id,
            reception_id=ReceptionId.parse(reception_id_value),
        )
        assert reloaded_reception is not None
        assert reloaded_reception.medication_history_id == history_id
