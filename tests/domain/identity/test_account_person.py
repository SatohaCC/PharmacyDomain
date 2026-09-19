"""本人の属性が変わっても操作主体の同一性を保つ。"""

from app.domain.identity.account_person import AccountPerson
from app.domain.identity.primitives import AccountPersonId
from app.domain.shared.person_name import PersonNames


def test_氏名変更で本人の識別子は変化しない() -> None:
    person = AccountPerson(
        id=AccountPersonId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
    )
    names = PersonNames.create(
        last_name="鈴木",
        first_name="太郎",
        last_name_kana="スズキ",
        first_name_kana="タロウ",
    )
    updated = person.change_names(names)
    assert updated.id == person.id
    assert updated.names == names
    assert person.names != names
