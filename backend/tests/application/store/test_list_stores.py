"""店舗一覧取得ユースケースのテスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.store.queries.list_stores import ListStoresUseCase
from app.application.store.queries.models import ListStoresQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.store.primitives import PublicExpenseDesignationNumber
from app.domain.store.value_objects import (
    CommunityLinkageCertification,
    PharmacyCertifications,
)
from app.infrastructure.readers.store_list_stores import ListStoresProjection
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.store.helpers import save_store
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository


async def test_list_stores_returns_summaries_of_the_requesting_corporate() -> None:
    # Arrange: 要求元法人に2件、別法人に1件を用意する
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    await save_store(
        repository, corporate_id=corporate_id, name="サンプル薬局", code="ST-001"
    )
    await save_store(repository, corporate_id=corporate_id, name="第二薬局")
    await save_store(repository, corporate_id=CorporateId.generate(), name="他法人薬局")
    use_case = ListStoresUseCase(
        reader=ListStoresProjection(repository),
        corporate_access=create_vendor_corporate_access(),
    )

    # Act
    actual = await use_case.execute(
        ListStoresQuery(corporate_id=str(corporate_id.value))
    )

    # Assert: 他法人の店舗が混ざらないこと
    assert len(actual) == 2
    assert {summary.name for summary in actual} == {"サンプル薬局", "第二薬局"}
    assert all(summary.corporate_id == str(corporate_id.value) for summary in actual)
    assert {summary.code for summary in actual} == {"ST-001", None}


async def test_list_stores_returns_empty_list_when_corporate_has_no_store() -> None:
    # Arrange
    repository = InMemoryStoreRepository()
    await save_store(repository, corporate_id=CorporateId.generate())
    use_case = ListStoresUseCase(
        reader=ListStoresProjection(repository),
        corporate_access=create_vendor_corporate_access(),
    )

    # Act
    actual = await use_case.execute(
        ListStoresQuery(corporate_id=str(CorporateId.generate().value))
    )

    # Assert
    assert actual == []


async def test_list_stores_evaluates_certification_validity_period() -> None:
    repository = InMemoryStoreRepository()
    corporate_id = CorporateId.generate()
    store = await save_store(repository, corporate_id=corporate_id, name="認定薬局")
    cert = PharmacyCertifications(
        community_linkage=CommunityLinkageCertification(
            certification_number=PublicExpenseDesignationNumber("1234567"),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
    )
    store = store.update_certifications(cert)
    await repository.save(store)

    # 1. 有効期間内 (2026-06-01): is_community_linkage == True
    clock_in_period = FakeClock(datetime(2026, 6, 1, 0, 0, tzinfo=UTC))
    use_case = ListStoresUseCase(
        reader=ListStoresProjection(repository, clock_in_period),
        corporate_access=create_vendor_corporate_access(),
    )
    results = await use_case.execute(
        ListStoresQuery(corporate_id=str(corporate_id.value))
    )
    assert len(results) == 1
    assert results[0].is_community_linkage is True

    # 2. 満了後 (2027-01-01): is_community_linkage == False
    clock_expired = FakeClock(datetime(2027, 1, 1, 0, 0, tzinfo=UTC))
    use_case_expired = ListStoresUseCase(
        reader=ListStoresProjection(repository, clock_expired),
        corporate_access=create_vendor_corporate_access(),
    )
    results_expired = await use_case_expired.execute(
        ListStoresQuery(corporate_id=str(corporate_id.value))
    )
    assert len(results_expired) == 1
    assert results_expired[0].is_community_linkage is False

    # 3. 開始前 (2025-12-31): is_community_linkage == False
    clock_before = FakeClock(datetime(2025, 12, 31, 0, 0, tzinfo=UTC))
    use_case_before = ListStoresUseCase(
        reader=ListStoresProjection(repository, clock_before),
        corporate_access=create_vendor_corporate_access(),
    )
    results_before = await use_case_before.execute(
        ListStoresQuery(corporate_id=str(corporate_id.value))
    )
    assert len(results_before) == 1
    assert results_before[0].is_community_linkage is False
