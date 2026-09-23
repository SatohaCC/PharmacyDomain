"""NSIPS受付取込の全集約書込みを実PostgreSQLの一トランザクションで検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import ClassVar

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
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryCommand,
    StartMedicationHistoryUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.shared.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet
from tests.factories.medicine_catalog_factory import create_medicine
from tests.integration.organization_helpers import appoint_manager, setup_organization

_NEW_ROWS: tuple[str, ...] = (
    "patients",
    "patient_external_identifiers",
    "patient_coverages",
    "coverage_selection_records",
    "prescriptions",
    "dispensing_processes",
    "medication_history_records",
)


class _LateIngestionFailure(RuntimeError):
    """薬歴を保存した直後に注入するテスト用の後段障害。"""


class _FailAfterMedicationHistorySave:
    """本番の薬歴UseCaseを実行後、同じUoW内の全行を確認して失敗する。"""

    _delegate: StartMedicationHistoryUseCase
    _session: AsyncSession
    _corporate_id: CorporateId
    observed_tables: ClassVar[tuple[str, ...]] = _NEW_ROWS

    def __init__(
        self,
        delegate: StartMedicationHistoryUseCase,
        session: AsyncSession,
        corporate_id: CorporateId,
    ) -> None:
        self._delegate = delegate
        self._session = session
        self._corporate_id = corporate_id

    async def execute(
        self, command: StartMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """実薬歴保存後に各テーブルを確認し、UoWへ失敗を返す。"""
        await self._delegate.execute(command)
        for table in self.observed_tables:
            count = await self._session.scalar(
                text(
                    f"SELECT count(*) FROM {table} WHERE corporate_id = :corporate_id"
                ),
                {"corporate_id": self._corporate_id.value},
            )
            assert count == 1, f"失敗注入前に {table} の書込みが完了していない。"
        raise _LateIngestionFailure("薬歴保存後の障害を注入した。")


def _bundle() -> NsipsBundle:
    """実UoWで患者・資格・処方・調剤・薬歴を作る構造化入力を返す。"""
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
async def test_薬歴保存後の失敗でNSIPS受付の全書込みがPostgreSQLから巻き戻る(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """患者から薬歴まで保存された後に失敗し、全新規行が残らない。"""
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
        operator_staff_id=str(organization.staff[0].id.value),
        structured_bundle=_bundle(),
    )

    request_scope = organization.root.request_scope(
        authorization=organization.authorization
    )
    with pytest.raises(_LateIngestionFailure):
        async with request_scope as scope:
            use_case = scope.use_cases.integration.ingest_nsips
            original = use_case._start_medication_history_use_case
            assert original is not None
            monkeypatch.setattr(
                use_case,
                "_start_medication_history_use_case",
                _FailAfterMedicationHistorySave(
                    original,
                    scope._unit_of_work.session,
                    organization.corporate.id,
                ),
            )
            await use_case.execute(command)

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
            for table in _NEW_ROWS
        }

    assert counts == dict.fromkeys(_NEW_ROWS, 0)
