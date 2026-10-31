"""identity集約のテスト用ファクトリ。"""

from __future__ import annotations

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import (
    AccountPerson,
    CorporateMembership,
    StaffPersonLink,
    UserAccount,
)
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import (
    AccountStatus,
    ExternalSubjectKey,
    MembershipRole,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


def create_person_names(
    last_name: str = "山田",
    first_name: str = "太郎",
    last_kana: str = "ヤマダ",
    first_kana: str = "タロウ",
) -> PersonNames:
    return PersonNames(
        kanji=PersonName(
            last_name=PersonNamePart(last_name),
            first_name=PersonNamePart(first_name),
        ),
        kana=PersonNameKana(
            last_name=PersonNameKanaPart(last_kana),
            first_name=PersonNameKanaPart(first_kana),
        ),
    )


def create_account_person(
    *,
    corporate_id: CorporateId | None = None,
    person_id: AccountPersonId | None = None,
    names: PersonNames | None = None,
) -> AccountPerson:
    return AccountPerson(
        id=person_id if person_id is not None else AccountPersonId.generate(),
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        names=names if names is not None else create_person_names(),
    )


def create_user_account(
    *,
    corporate_id: CorporateId | None = None,
    account_id: UserAccountId | None = None,
    person_id: AccountPersonId | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
    external_subject: ExternalSubjectKey | str | None = None,
    is_vendor_admin: bool = False,
) -> UserAccount:
    ext_sub = (
        ExternalSubjectKey(external_subject)
        if isinstance(external_subject, str)
        else external_subject
    )
    return UserAccount(
        id=account_id if account_id is not None else UserAccountId.generate(),
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        person_id=person_id if person_id is not None else AccountPersonId.generate(),
        status=status,
        external_subject=ext_sub,
        is_vendor_admin=is_vendor_admin,
    )


def create_corporate_membership(
    *,
    corporate_id: CorporateId,
    account_id: UserAccountId,
    membership_id: CorporateMembershipId | None = None,
    role: MembershipRole = MembershipRole.STORE_OPERATOR,
    store_ids: frozenset[StoreId] = frozenset(),
    staff_id: StaffId | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> CorporateMembership:
    return CorporateMembership(
        id=membership_id
        if membership_id is not None
        else CorporateMembershipId.generate(),
        account_id=account_id,
        corporate_id=corporate_id,
        role=role,
        store_ids=store_ids,
        staff_id=staff_id,
        status=status,
    )


def create_staff_person_link(
    *,
    corporate_id: CorporateId,
    staff_id: StaffId,
    person_id: AccountPersonId,
) -> StaffPersonLink:
    return StaffPersonLink(
        id=staff_id,
        corporate_id=corporate_id,
        person_id=person_id,
    )
