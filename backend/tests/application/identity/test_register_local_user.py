"""利用者登録の認可・本人検証・資格情報発行を実オブジェクトで確認する。"""

from dataclasses import replace

import pytest

from app.application.access_control.models import ActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import NotFoundError
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.identity.local_authentication import CredentialWriter
from app.application.identity.register_local_user import (
    RegisterLocalUserCommand,
    RegisterLocalUserUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.entities import AccountPerson, UserAccount
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access,
)
from tests.application.identity.helpers import (
    IdentityUseCaseSet,
    create_identity_use_cases,
)
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.null_unit_of_work import NullUnitOfWork


class RecordingCredentialWriter(CredentialWriter):
    """発行要求を記録し、保存失敗を明示的に再現する。"""

    def __init__(self, *, fail: bool = False) -> None:
        self.issued: list[tuple[str, str, str]] = []
        self.fail = fail

    async def issue(self, login_id: str, password: str, subject: str) -> None:
        if self.fail:
            raise IdentityConflictError("ログインIDが重複しています。")
        self.issued.append((login_id, password, subject))


async def setup_registration() -> tuple[IdentityUseCaseSet, RegisterLocalUserCommand]:
    """未登録の本人と登録入力を用意する。"""
    fixture = create_identity_use_cases()
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("テスト"), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("テスト"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
    )
    await fixture.repositories.people.save(person)
    return fixture, RegisterLocalUserCommand(
        corporate_id=str(CorporateId.generate().value),
        person_id=str(person.id.value),
        login_id="test-admin",
        initial_password="test-initial-password-12345",
    )


def service(
    fixture: IdentityUseCaseSet,
    writer: RecordingCredentialWriter,
    access: CorporateAccessService | None = None,
) -> RegisterLocalUserUseCase:
    """実Repositoryと明示的な認可境界を接続する。"""
    return RegisterLocalUserUseCase(
        fixture.repositories,
        fixture.staff,
        fixture.stores,
        access or create_vendor_corporate_access(),
        NullUnitOfWork(),
        FakeOrganizationLock(),
        writer,
    )


@pytest.mark.asyncio
async def test_利用者登録_本人と資格情報と法人管理者権限を同じアカウントへ結び付ける() -> (
    None
):
    # Arrange
    fixture, command = await setup_registration()
    writer = RecordingCredentialWriter()
    # Act
    result = await service(fixture, writer).execute(command)
    # Assert
    account = await fixture.repositories.accounts.get(UserAccountId.parse(result.id))
    assert account is not None and not account.is_vendor_admin
    assert str(account.person_id.value) == command.person_id
    assert account.external_subject is not None
    assert writer.issued == [
        (command.login_id, command.initial_password, account.external_subject.value)
    ]
    membership = await fixture.repositories.memberships.find_active_for_account(
        account.id
    )
    assert membership is not None
    assert str(membership.corporate_id.value) == command.corporate_id
    assert membership.role.value == "corporate_admin"


@pytest.mark.asyncio
async def test_利用者登録_他法人の管理者は本人と資格情報を保存できない() -> None:
    # Arrange
    fixture, command = await setup_registration()
    writer = RecordingCredentialWriter()
    access = CorporateAccessService(
        AutoProvisioningCorporateRepository(),
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="test-admin", corporate_id=CorporateId.generate()
            )
        ),
    )
    # Act / Assert
    with pytest.raises(NotFoundError):
        await service(fixture, writer, access).execute(command)
    assert writer.issued == []
    assert (
        await fixture.repositories.accounts.get_by_person(
            AccountPersonId.parse(command.person_id)
        )
        is None
    )


@pytest.mark.asyncio
async def test_利用者登録_存在しない本人の資格情報を発行しない() -> None:
    # Arrange
    fixture, command = await setup_registration()
    writer = RecordingCredentialWriter()
    # Act / Assert
    with pytest.raises(NotFoundError):
        await service(fixture, writer).execute(
            replace(command, person_id=str(AccountPersonId.generate().value))
        )
    assert writer.issued == []


@pytest.mark.asyncio
async def test_利用者登録_既存アカウントの資格情報を付け替えない() -> None:
    # Arrange
    fixture, command = await setup_registration()
    writer = RecordingCredentialWriter()
    await fixture.repositories.accounts.save(
        UserAccount(
            id=UserAccountId.generate(),
            person_id=AccountPersonId.parse(command.person_id),
        )
    )
    # Act / Assert
    with pytest.raises(IdentityConflictError):
        await service(fixture, writer).execute(command)
    assert writer.issued == []


@pytest.mark.asyncio
async def test_利用者登録_スタッフのない店舗権限は資格情報発行前に拒否する() -> None:
    # Arrange
    fixture, command = await setup_registration()
    writer = RecordingCredentialWriter()
    # Act / Assert
    with pytest.raises(DomainValidationError):
        await service(fixture, writer).execute(replace(command, role="store_viewer"))
    assert writer.issued == []
    assert (
        await fixture.repositories.accounts.get_by_person(
            AccountPersonId.parse(command.person_id)
        )
        is None
    )


@pytest.mark.asyncio
async def test_利用者登録_資格情報保存の失敗を伝播して法人権限を確定しない() -> None:
    """UoWへ例外を伝播する。実際のロールバックは実DBの結合テストで確認する。"""
    # Arrange
    fixture, command = await setup_registration()
    # Act / Assert
    with pytest.raises(IdentityConflictError):
        await service(fixture, RecordingCredentialWriter(fail=True)).execute(command)
    assert (
        await fixture.repositories.memberships.list_by_corporate(
            CorporateId.parse(command.corporate_id)
        )
        == []
    )
