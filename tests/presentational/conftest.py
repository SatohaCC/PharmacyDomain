"""HTTP境界テストの土台。

DBもトランザクション境界も通さない。``PostgresRequestScope`` の振る舞いは
``tests/infrastructure/test_composition.py`` が固定しており、ここで確かめたいのは
「ルート・認証・例外翻訳の結線」だけである。そのためユースケース束の依存だけを
インメモリ実装へ差し替える。

処方箋・調剤・薬歴は参照Boundaryを多数必要とするため、この土台には載せず、
``tests/application/*/helpers.py`` の Fixture を再利用する
（``test_http_routes_clinical.py``）。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.presentational import create_app
from app.presentational.dependencies import (
    get_corporate_use_cases,
    get_coverage_use_cases,
    get_medicine_catalog_use_cases,
    get_patient_use_cases,
    get_reception_use_cases,
    get_staff_use_cases,
    get_store_use_cases,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)
from tests.fakes.in_memory_patient_coverage_repository import (
    InMemoryPatientCoverageRepository,
)
from tests.fakes.in_memory_patient_repository import (
    InMemoryPatientExternalIdentifierRepository,
    InMemoryPatientRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.stub_actor_context_provider import (
    VALID_TOKEN,
    StubActorContextProvider,
)
from tests.presentational.helpers import (
    create_corporate_use_cases,
    create_coverage_use_cases,
    create_medicine_catalog_use_cases,
    create_patient_use_cases,
    create_reception_use_cases,
    create_staff_use_cases,
    create_store_use_cases,
    vendor_admin,
)

#: 認証を通すリクエストヘッダ。
AUTHORIZED_HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@dataclass(frozen=True, slots=True)
class Api:
    """テスト対象のクライアントと、その裏側の保管庫。"""

    client: TestClient
    corporates: InMemoryCorporateRepository
    stores: InMemoryStoreRepository
    staffs: InMemoryStaffRepository
    patients: InMemoryPatientRepository
    external_identifiers: InMemoryPatientExternalIdentifierRepository
    coverages: InMemoryPatientCoverageRepository
    selection_records: InMemoryCoverageSelectionRecordRepository
    medicines: InMemoryMedicineCatalogRepository
    clock: FakeClock


@pytest.fixture
def api() -> Iterator[Api]:
    """インメモリ実装へ差し替えたアプリケーションのクライアントを返す。"""
    corporates = InMemoryCorporateRepository()
    stores = InMemoryStoreRepository()
    staffs = InMemoryStaffRepository()
    patients = InMemoryPatientRepository()
    external_identifiers = InMemoryPatientExternalIdentifierRepository()
    coverages = InMemoryPatientCoverageRepository()
    selection_records = InMemoryCoverageSelectionRecordRepository()
    medicines = InMemoryMedicineCatalogRepository()
    clock = FakeClock()

    app = create_app(actor_provider=StubActorContextProvider(vendor_admin()))
    app.dependency_overrides.update(
        {
            get_corporate_use_cases: lambda: create_corporate_use_cases(corporates),
            get_store_use_cases: lambda: create_store_use_cases(stores, corporates),
            get_staff_use_cases: lambda: create_staff_use_cases(
                staffs, stores, corporates, clock
            ),
            get_patient_use_cases: lambda: create_patient_use_cases(
                patients, external_identifiers, corporates
            ),
            get_coverage_use_cases: lambda: create_coverage_use_cases(
                coverages, patients, corporates
            ),
            get_reception_use_cases: lambda: create_reception_use_cases(
                selection_records, stores, patients, coverages, corporates, clock
            ),
            get_medicine_catalog_use_cases: lambda: create_medicine_catalog_use_cases(
                medicines
            ),
        }
    )

    # lifespanは起動しない。起動するとDB接続を要求してしまい、HTTPの結線だけを
    # 確かめたいテストが PostgreSQL の有無に左右される。
    yield Api(
        client=TestClient(app),
        corporates=corporates,
        stores=stores,
        staffs=staffs,
        patients=patients,
        external_identifiers=external_identifiers,
        coverages=coverages,
        selection_records=selection_records,
        medicines=medicines,
        clock=clock,
    )
    app.dependency_overrides.clear()
