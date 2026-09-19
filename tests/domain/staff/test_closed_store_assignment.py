"""閉局済み店舗への新たな配属を禁止する。"""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.foundation.exceptions import DomainError
from app.domain.staff.services import StaffStoreAssignmentService
from app.domain.store.lifecycle import StoreStatus
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store


@pytest.mark.parametrize("status", list(StoreStatus))
@pytest.mark.parametrize("method", ["assign_home_store", "assign_concurrent_store"])
def test_閉局だけを新規配属の対象から外す(status: StoreStatus, method: str) -> None:
    staff = create_staff()
    store = replace(create_store(corporate_id=staff.corporate_id), status=status)
    operation = getattr(StaffStoreAssignmentService(), method)
    if status == StoreStatus.CLOSED:
        with pytest.raises(DomainError):
            operation(staff, store, date(2026, 9, 17))
    else:
        assigned = operation(staff, store, date(2026, 9, 17))
        assert assigned.affiliations[-1].store_id == store.id
