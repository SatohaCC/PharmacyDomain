"""本人の名前から対応を推測せず、明示登録したStaff参照を確認する。"""

from dataclasses import replace

import pytest

from app.application.common.exceptions import NotFoundError
from app.application.identity.commands.models import PersonNamesInput
from app.application.identity.commands.services.support import (
    validate_membership_target,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.primitives import MembershipRole
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.primitives import StaffStatus
from tests.application.identity.helpers import _setup
from tests.factories.staff_factory import create_staff


@pytest.mark.asyncio
async def test_同名の本人を登録しても一人へ統合しない() -> None:
    fixture = await _setup()
    created = await fixture.service.register_person.execute(
        fixture.command.corporate_id,
        PersonNamesInput(
            last_name=fixture.person.names.kanji.last_name.value,
            first_name=fixture.person.names.kanji.first_name.value,
            last_name_kana=fixture.person.names.kana.last_name.value,
            first_name_kana=fixture.person.names.kana.first_name.value,
        ),
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
    assert link.corporate_id == corporate_id
    assert link.person_id == fixture.person.id
    assert link.id == staff.id
    saved_link = await fixture.repositories.links.get(staff.id)
    assert saved_link is not None
    assert saved_link.corporate_id == corporate_id
    assert saved_link.person_id == fixture.person.id
    other = replace(fixture.person, id=AccountPersonId.generate())
    await fixture.repositories.people.save(other)
    with pytest.raises(IdentityConflictError):
        await fixture.service.link_staff.execute(
            str(corporate_id.value), str(other.id.value), str(staff.id.value)
        )
    actual = await fixture.repositories.links.get(staff.id)
    assert actual is not None and actual.person_id == fixture.person.id


@pytest.mark.asyncio
async def test_スタッフ本人リンク_同じ対応を再実行すると一件のまま成功する() -> None:
    fixture = await _setup()
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    staff = create_staff(corporate_id=corporate_id)
    await fixture.service.staff.save(staff)

    first = await fixture.service.link_staff.execute(
        str(corporate_id.value), str(fixture.person.id.value), str(staff.id.value)
    )
    second = await fixture.service.link_staff.execute(
        str(corporate_id.value), str(fixture.person.id.value), str(staff.id.value)
    )

    assert first == second
    assert first.corporate_id == corporate_id
    assert first.person_id == fixture.person.id
    assert first.id == staff.id
    saved_link = await fixture.repositories.links.get(staff.id)
    assert saved_link is not None
    assert saved_link.person_id == fixture.person.id


@pytest.mark.asyncio
async def test_スタッフ本人リンク_別法人スタッフと未存在スタッフはNotFoundとなりリンクを作らない() -> (
    None
):
    fixture = await _setup()
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    foreign_staff = create_staff(corporate_id=CorporateId.generate())
    await fixture.service.staff.save(foreign_staff)
    missing_staff_id = create_staff(corporate_id=corporate_id).id

    results: list[type[Exception]] = []
    for staff_id in (foreign_staff.id, missing_staff_id):
        with pytest.raises(NotFoundError) as error:
            await fixture.service.link_staff.execute(
                str(corporate_id.value),
                str(fixture.person.id.value),
                str(staff_id.value),
            )
        results.append(type(error.value))
        assert await fixture.repositories.links.get(staff_id) is None

    assert results == [NotFoundError, NotFoundError]


@pytest.mark.asyncio
async def test_スタッフ本人リンク_別法人本人と未存在本人は同じNotFoundでリンクを作らない() -> (
    None
):
    fixture = await _setup()
    corporate_id = CorporateId.parse(fixture.command.corporate_id)
    staff = create_staff(corporate_id=corporate_id)
    await fixture.service.staff.save(staff)
    foreign_person = replace(
        fixture.person,
        id=AccountPersonId.generate(),
        corporate_id=CorporateId.generate(),
    )
    await fixture.repositories.people.save(foreign_person)
    missing_person_id = AccountPersonId.generate()

    observed: list[type[Exception]] = []
    for person_id in (foreign_person.id, missing_person_id):
        with pytest.raises(NotFoundError) as error:
            await fixture.service.link_staff.execute(
                str(corporate_id.value), str(person_id.value), str(staff.id.value)
            )
        observed.append(type(error.value))
        assert await fixture.repositories.links.get(staff.id) is None

    assert observed == [NotFoundError, NotFoundError]


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["別法人", "別人", "未対応", "退職"])
async def test_店舗ロールの付与には同一法人で本人に対応する有効スタッフが必要(
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
        await fixture.service.staff.save(replace(staff, status=StaffStatus.RETIRED))
    with pytest.raises(
        NotFoundError if violation == "別法人" else IdentityConflictError
    ):
        await validate_membership_target(
            person_id=fixture.person.id,
            corporate_id=corporate_id,
            role=MembershipRole.MEMBER,
            store_ids=frozenset(),
            staff_id=staff.id,
            staff=fixture.service.staff,
            stores=fixture.service.stores,
            links=fixture.repositories.links,
        )
