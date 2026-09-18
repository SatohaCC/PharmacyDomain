"""法人所属が変わっても維持される操作者本人。"""

from dataclasses import dataclass, replace

from app.domain.foundation.entity import AggregateRoot
from app.domain.identity.primitives import AccountPersonId
from app.domain.shared.person_name import PersonNames


@dataclass(frozen=True, eq=False, kw_only=True)
class AccountPerson(AggregateRoot[AccountPersonId]):
    """アカウントを使用する一人の人。"""

    id: AccountPersonId
    names: PersonNames

    def change_names(self, names: PersonNames) -> AccountPerson:
        """本人の同一性を保ち氏名を変更する。"""
        return replace(self, names=names)
