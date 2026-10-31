"""NSIPS原本参照ユースケースのテスト (TC-129, TC-103, TC-135)。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.integration.boundary_models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
)
from app.application.integration.commands.ingest_nsips import IngestNsipsCommand
from app.application.integration.queries.get_nsips_source import (
    GetNsipsSourceUseCase,
)
from app.application.integration.queries.models import GetNsipsSourceQuery
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.integration_nsips_source import (
    PostgresGetNsipsSourceQueryReader,
)
from tests.application.integration.nsips.helpers import (
    create_fixture,
    execute_structured_test_command,
)


@pytest.mark.asyncio
async def test_TC129_原本GETで処方記載事項や算定加算が欠落なく投影される() -> None:
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = NsipsBundle(
        header_version="structured-test",
        patient=NsipsPatientInfo(
            external_patient_id="P-TC129",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-TC129",
            issued_date=date(2026, 9, 21),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日3回毎食後",
                    dispensing_quantity=14,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="アスピリン",
                            dosage=Decimal("100"),
                            unit="mg",
                        ),
                    ),
                ),
            ),
        ),
        dispensed_date=date(2026, 9, 21),
        insurance=NsipsInsuranceInfo(
            insurer_number="12345678",
            insured_symbol="記号",
            insured_number="1234",
            branch_number="01",
            benefit_ratio=30,
        ),
        additions=(
            NsipsAdditionInfo(
                code="ADD-01",
                name="調剤基本料1",
                points=42,
                quantity=1,
            ),
        ),
    )
    ingest_result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )
    assert ingest_result.prescription_id is None
    assert ingest_result.dispensing_id is None
    assert ingest_result.source_status == "current"

    reader = PostgresGetNsipsSourceQueryReader(
        reception_repository=fixture.reception_repo,
        medication_history_repository=fixture.medication_history_repo,
    )
    use_case = GetNsipsSourceUseCase(
        reader=reader,
        corporate_access=fixture.use_case._corporate_access,
    )

    query = GetNsipsSourceQuery(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        reception_id=str(reception_id.value),
    )
    dto = await use_case.execute(query)

    assert dto.reception_id == str(reception_id.value)
    assert dto.corporate_id == str(fixture.corporate_id.value)
    assert dto.store_id == str(fixture.store_id.value)
    assert dto.source_status == "current"
    assert dto.source_fingerprint == ingest_result.source_fingerprint
    assert dto.dispensed_date == "2026-09-21"
    assert dto.prescription is not None
    assert dto.prescription.document_number == "DOC-TC129"
    assert dto.prescription.institution_name == "中央診療所"
    assert len(dto.prescription.rps) == 1
    assert dto.prescription.rps[0].medicines[0].medicine_name == "アスピリン"
    assert dto.insurance is not None
    assert dto.insurance.insurer_number == "12345678"
    assert len(dto.additions) == 1
    assert dto.additions[0].name == "調剤基本料1"
    assert dto.prescription_id is None
    assert dto.dispensing_id is None
    assert not dto.has_pending_correction_review


@pytest.mark.asyncio
async def test_TC103_他店舗の原本GETは404で隠蔽される() -> None:
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    bundle = NsipsBundle(
        header_version="structured-test",
        patient=NsipsPatientInfo(
            external_patient_id="P-TC103",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number="DOC-TC103",
            issued_date=date(2026, 9, 21),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code=None,
            department_name=None,
            doctor_name="佐藤医師",
            rps=(),
        ),
    )
    await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(reception_id.value),
            structured_bundle=bundle,
        ),
    )

    reader = PostgresGetNsipsSourceQueryReader(
        reception_repository=fixture.reception_repo,
        medication_history_repository=fixture.medication_history_repo,
    )
    use_case = GetNsipsSourceUseCase(
        reader=reader,
        corporate_access=fixture.use_case._corporate_access,
    )

    # 存在しない他店舗IDで要求 -> 404 TenantBoundaryNotFoundError
    other_store_id = StoreId.generate()
    with pytest.raises(TenantBoundaryNotFoundError):
        await use_case.execute(
            GetNsipsSourceQuery(
                corporate_id=str(fixture.corporate_id.value),
                store_id=str(other_store_id.value),
                reception_id=str(reception_id.value),
            )
        )
