"""通常業務の保存時に法人停止を再確認する境界の検証。"""

import pytest

from app.application.composition.corporate_activity_guard import (
    CorporateActivityWriteGuard,
)
from app.application.corporate.exceptions import (
    CorporateInactiveError,
    CorporateNotFoundError,
)
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId
from tests.application.corporate.helpers import create_corporate
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


class 読み出し順序検証Repository(InMemoryCorporateRepository):
    """法人を読む前に同じ法人のロックが取得されていることを確認する。"""

    def __init__(self, lock: FakeOrganizationLock) -> None:
        super().__init__()
        self._lock = lock

    async def get(self, corporate_id: CorporateId) -> Corporate | None:
        assert self._lock.keys == [f"corporate:{corporate_id.value}"]
        return await super().get(corporate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["store", "staff", "prescription", "definition"])
@pytest.mark.parametrize("is_new", [True, False])
@pytest.mark.parametrize("active", [True, False])
async def test_通常業務の保存_ロック後に法人状態を読み_停止済みなら拒否する(
    kind: str, is_new: bool, active: bool
) -> None:
    # Arrange
    lock = FakeOrganizationLock()
    repository = 読み出し順序検証Repository(lock)
    corporate = create_corporate()
    await repository.save(corporate if active else corporate.deactivate())
    aggregates = {
        "store": create_store(corporate_id=corporate.id),
        "staff": create_staff(corporate_id=corporate.id),
        "prescription": create_prescription(corporate_id=corporate.id),
        "definition": EventDefinition.create_custom(
            corporate_id=corporate.id, name=EventTypeName("相談")
        ),
    }
    guard = CorporateActivityWriteGuard(repository, lock)

    # Act / Assert
    if active:
        await guard.check(aggregates[kind], is_new)
    else:
        with pytest.raises(CorporateInactiveError):
            await guard.check(aggregates[kind], is_new)
    assert lock.keys == [f"corporate:{corporate.id.value}"]


@pytest.mark.asyncio
async def test_通常業務の保存_法人が存在しない_拒否する() -> None:
    # Arrange
    lock = FakeOrganizationLock()
    repository = 読み出し順序検証Repository(lock)
    corporate_id = CorporateId.generate()
    guard = CorporateActivityWriteGuard(repository, lock)

    # Act / Assert
    with pytest.raises(CorporateNotFoundError):
        await guard.check(create_store(corporate_id=corporate_id), True)


@pytest.mark.asyncio
async def test_標準マスタと法人自身_保存時の有効状態確認を適用しない() -> None:
    # Arrange
    lock = FakeOrganizationLock()
    guard = CorporateActivityWriteGuard(InMemoryCorporateRepository(), lock)
    standard = EventDefinition.create_standard(
        code=EventTypeStandardCode("visit"), name=EventTypeName("来局")
    )

    # Act
    await guard.check(standard, True)
    await guard.check(create_corporate().deactivate(), False)

    # Assert
    assert lock.keys == []
