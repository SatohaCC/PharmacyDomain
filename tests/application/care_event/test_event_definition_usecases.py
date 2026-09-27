"""法人独自イベント種別の認可と更新。"""

from __future__ import annotations

import pytest

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.application.access_control.policy import AuthorizationService
from app.application.care_event.event_definition import (
    CreateEventDefinitionCommand,
    CreateEventDefinitionUseCase,
    ListEventDefinitionsUseCase,
    UpdateEventDefinitionCommand,
    UpdateEventDefinitionUseCase,
)
from app.application.common.exceptions import (
    ApplicationError,
    AuthorizationError,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import (
    EventTypeId,
    EventTypeName,
    EventTypeStandardCode,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import AutoProvisioningCorporateRepository
from tests.fakes.in_memory_event_definition_repository import (
    InMemoryEventDefinitionRepository,
)


def _access(actor: ActorContext) -> CorporateAccessService:
    return CorporateAccessService(
        AutoProvisioningCorporateRepository(), AuthorizationService(actor)
    )


def _store_actor(*, corporate_id: CorporateId, role: ActorRole) -> ResolvedActorContext:
    return ResolvedActorContext(
        principal_id="店舗担当者",
        roles=frozenset({role}),
        corporate_id=corporate_id,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        staff_id=StaffId.generate(),
        store_ids=frozenset({StoreId.generate()}),
    )


async def test_tc45_02_法人管理者が作成と改名を行う() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryEventDefinitionRepository()
    access = _access(
        ActorContext.corporate_admin(
            principal_id="法人管理者", corporate_id=corporate_id
        )
    )
    create = CreateEventDefinitionUseCase(repository, access)
    update = UpdateEventDefinitionUseCase(repository, access)

    created = await create.execute(
        CreateEventDefinitionCommand(
            corporate_id=str(corporate_id.value), name="服薬中の相談"
        )
    )
    renamed = await update.execute(
        UpdateEventDefinitionCommand(
            corporate_id=str(corporate_id.value),
            event_type_id=created.id,
            name="服薬継続の相談",
        )
    )

    assert renamed.id == created.id
    assert renamed.corporate_id == str(corporate_id.value)
    assert renamed.name == "服薬継続の相談"
    assert renamed.is_active


@pytest.mark.parametrize("role", [ActorRole.STORE_OPERATOR, ActorRole.STORE_VIEWER])
async def test_tc45_06_店舗ロールは法人独自種別を変更できない(
    role: ActorRole,
) -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryEventDefinitionRepository()
    definition = EventDefinition(
        id=EventTypeId.generate(),
        name=EventTypeName("店舗では変更できない種別"),
        corporate_id=corporate_id,
    )
    await repository.save(definition)
    create = CreateEventDefinitionUseCase(
        repository,
        _access(_store_actor(corporate_id=corporate_id, role=role)),
    )
    update = UpdateEventDefinitionUseCase(
        repository,
        _access(_store_actor(corporate_id=corporate_id, role=role)),
    )

    with pytest.raises(AuthorizationError):
        await create.execute(
            CreateEventDefinitionCommand(
                corporate_id=str(corporate_id.value), name="店舗独自の相談"
            )
        )
    for command in (
        UpdateEventDefinitionCommand(
            corporate_id=str(corporate_id.value),
            event_type_id=str(definition.id.value),
            name="不正な改名",
        ),
        UpdateEventDefinitionCommand(
            corporate_id=str(corporate_id.value),
            event_type_id=str(definition.id.value),
            is_active=False,
        ),
    ):
        with pytest.raises(AuthorizationError):
            await update.execute(command)

    assert repository.items[definition.id] == definition


async def test_tc45_06_他法人管理者から種別の存在を隠す() -> None:
    corporate_id = CorporateId.generate()
    other_corporate_id = CorporateId.generate()
    repository = InMemoryEventDefinitionRepository()
    definition = EventDefinition(
        id=EventTypeId.generate(),
        name=EventTypeName("他法人の種別"),
        corporate_id=other_corporate_id,
    )
    await repository.save(definition)
    use_case = UpdateEventDefinitionUseCase(
        repository,
        _access(
            ActorContext.corporate_admin(
                principal_id="法人管理者", corporate_id=corporate_id
            )
        ),
    )

    with pytest.raises(ApplicationError):
        await use_case.execute(
            UpdateEventDefinitionCommand(
                corporate_id=str(corporate_id.value),
                event_type_id=str(definition.id.value),
                name="不正な改名",
            )
        )

    assert repository.items[definition.id].name.value == "他法人の種別"


async def test_tc45_07_店舗閲覧者には標準と自法人種別だけを返す() -> None:
    corporate_id = CorporateId.generate()
    other_corporate_id = CorporateId.generate()
    repository = InMemoryEventDefinitionRepository()
    definitions = (
        EventDefinition(
            id=EventTypeId.generate(),
            name=EventTypeName("処方箋受付"),
            standard_code=EventTypeStandardCode("prescription_reception"),
        ),
        EventDefinition(
            id=EventTypeId.generate(),
            name=EventTypeName("自法人の相談"),
            corporate_id=corporate_id,
        ),
        EventDefinition(
            id=EventTypeId.generate(),
            name=EventTypeName("他法人の相談"),
            corporate_id=other_corporate_id,
        ),
    )
    for definition in definitions:
        await repository.save(definition)
    use_case = ListEventDefinitionsUseCase(
        repository,
        _access(_store_actor(corporate_id=corporate_id, role=ActorRole.STORE_VIEWER)),
    )

    actual = await use_case.execute(str(corporate_id.value))

    assert {item.name for item in actual} == {"処方箋受付", "自法人の相談"}


async def test_tc45_04_法人内で重複する表示名を拒否する() -> None:
    corporate_id = CorporateId.generate()
    repository = InMemoryEventDefinitionRepository()
    access = _access(
        ActorContext.corporate_admin(
            principal_id="法人管理者", corporate_id=corporate_id
        )
    )
    use_case = CreateEventDefinitionUseCase(repository, access)
    command = CreateEventDefinitionCommand(
        corporate_id=str(corporate_id.value), name="薬の使い方相談"
    )
    await use_case.execute(command)

    with pytest.raises(DomainError):
        await use_case.execute(command)
