"""本人の名前から対応を推測せず、明示登録したStaff参照を確認する。"""

from dataclasses import replace

import pytest

from app.application.common.exceptions import NotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import AccountPersonId, MembershipRole
from tests.application.identity.test_invitation_management import _setup
from tests.factories.staff_factory import create_staff


@pytest.mark.asyncio
async def test_同名の本人を登録しても一人へ統合しない() -> None:
    fixture = await _setup()
    created = await fixture.service.register_person.execute(
        fixture.command.corporate_id, fixture.person.names
    )
    assert created.id != fixture.person.id
    assert created.names == fixture.person.names
    assert await fixture.repositories.people.get(fixture.person.id) == fixture.person


@pytest.mark.asyncio
async def test_スタッフに一度対応させた本人を別人へ付け替えない() -> None:
    fixture = await _setup()
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    staff = create_staff(corporate_id=corporate_id)
    await fixture.service.staff.save(staff)
    link = await fixture.service.link_staff.execute(
        str(corporate_id.value), str(fixture.person.id.value), str(staff.id.value)
    )
    assert link.person_id == fixture.person.id
    other = replace(fixture.person, id=AccountPersonId.generate())
    await fixture.repositories.people.save(other)
    with pytest.raises(IdentityConflictError):
        await fixture.service.link_staff.execute(
            str(corporate_id.value), str(other.id.value), str(staff.id.value)
        )
    actual = await fixture.repositories.links.get(staff.id)
    assert actual is not None and actual.person_id == fixture.person.id


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["別法人", "別人", "未対応", "退職"])
async def test_店舗ロールの招待には同一法人で本人に対応する有効スタッフが必要(
    violation: str,
) -> None:
    fixture = await _setup()
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    staff = create_staff(
        corporate_id=CorporateId.generate() if violation == "別法人" else corporate_id
    )
    await fixture.service.staff.save(staff)
    if violation not in {"別法人", "未対応"}:
        person = (
            replace(fixture.person, id=AccountPersonId.generate())
            if violation == "別人"
            else fixture.person
        )
        await fixture.repositories.people.save(person)
        await fixture.service.link_staff.execute(
            str(corporate_id.value), str(person.id.value), str(staff.id.value)
        )
    if violation == "退職":
        await fixture.service.staff.save(replace(staff, is_active=False))
    command = replace(
        fixture.command,
        role=MembershipRole.STORE_OPERATOR,
        staff_id=str(staff.id.value),
    )
    with pytest.raises(
        NotFoundError if violation == "別法人" else IdentityConflictError
    ):
        await fixture.service.invite.execute(command)
