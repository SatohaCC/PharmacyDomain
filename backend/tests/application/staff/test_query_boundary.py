"""スタッフ参照の事前認可と業務日の責務を検証する。"""

from datetime import UTC, date, datetime

import pytest

from app.application.corporate.errors import CorporateInactiveError
from app.application.staff.interfaces.get_staff_query_reader import GetStaffQueryReader
from app.application.staff.queries.dtos.get_staff import StaffDto
from app.application.staff.queries.dtos.list_staffs import StaffSummaryDto
from app.application.staff.queries.get_staff import GetStaffUseCase
from app.application.staff.queries.models import GetStaffQuery
from app.domain.corporate.identifiers import CorporateId
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.factories.staff_factory import create_staff
from tests.fakes.fake_clock import FakeClock


class RecordingStaffReader(GetStaffQueryReader):
    """参照条件を観測し、実DTOを返す読取フェイク。"""

    def __init__(self) -> None:
        self.calls = 0
        self.target_date: date | None = None
        self.include_private = False
        self.result = StaffSummaryDto.from_entity(create_staff())

    async def read(
        self, query: GetStaffQuery, *, include_private: bool, target_date: date | None
    ) -> StaffDto | StaffSummaryDto:
        self.calls += 1
        self.target_date = target_date
        self.include_private = include_private
        return self.result


@pytest.mark.asyncio
async def test_スタッフ参照_無効法人なら_Readerを呼ばない() -> None:
    # Arrange
    repository = AutoProvisioningCorporateRepository()
    corporate_id = CorporateId.generate()
    repository.set_inactive(corporate_id)
    reader = RecordingStaffReader()
    use_case = GetStaffUseCase(
        reader, create_vendor_corporate_access_for(repository), FakeClock()
    )
    query = GetStaffQuery(
        corporate_id=str(corporate_id.value), staff_id=reader.result.id
    )
    # Act / Assert
    with pytest.raises(CorporateInactiveError):
        await use_case.execute(query)
    assert reader.calls == 0


@pytest.mark.asyncio
async def test_スタッフ参照_UTCの日付境界を跨ぐと_日本時間の業務日をReaderへ渡す() -> (
    None
):
    # Arrange
    reader = RecordingStaffReader()
    clock = FakeClock(datetime(2026, 1, 1, 18, tzinfo=UTC))
    repository = AutoProvisioningCorporateRepository()
    use_case = GetStaffUseCase(
        reader, create_vendor_corporate_access_for(repository), clock
    )
    query = GetStaffQuery(
        corporate_id=str(CorporateId.generate().value), staff_id=reader.result.id
    )
    # Act
    await use_case.execute(query)
    # Assert
    assert reader.target_date == date(2026, 1, 2)
    assert reader.include_private is True
    assert clock.calls == 1
