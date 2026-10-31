"""本人の属性が変わっても操作主体の同一性を保つ。"""

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import AccountPerson
from app.domain.shared.actor import AccountPersonId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)


def test_氏名変更で本人の識別子は変化しない() -> None:
    corporate_id = CorporateId.generate()
    person = AccountPerson(
        id=AccountPersonId.generate(),
        corporate_id=corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
    )
    names = PersonNames(
        kanji=PersonName(
            last_name=PersonNamePart("鈴木"), first_name=PersonNamePart("太郎")
        ),
        kana=PersonNameKana(
            last_name=PersonNameKanaPart("スズキ"),
            first_name=PersonNameKanaPart("タロウ"),
        ),
    )
    updated = person.change_names(names)
    assert updated.id == person.id
    assert updated.names == names
    assert person.names != names
