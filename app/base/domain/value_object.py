from dataclasses import dataclass
from typing import Self

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.person_primitives import (
    BasePersonName,
    BasePersonNameKana,
)


@dataclass(frozen=True, kw_only=True)
class PersonName:
    """人名（漢字）を表す複合 Value Object"""

    last_name: BasePersonName  # 姓（例: 山田）
    first_name: BasePersonName  # 名（例: 太郎）

    def __post_init__(self) -> None:
        """姓と名が人名プリミティブで構成されていることを検証する。"""
        if not isinstance(self.last_name, BasePersonName):
            raise DomainValidationError("姓は BasePersonName で指定してください。")
        if not isinstance(self.first_name, BasePersonName):
            raise DomainValidationError("名は BasePersonName で指定してください。")

    @property
    def full_name(self) -> str:
        """フルネームを取得（スペース区切り）"""
        return f"{self.last_name.value} {self.first_name.value}"

    @classmethod
    def create(cls, *, last_name: str, first_name: str) -> Self:
        """未加工文字列から生成するファクトリ"""
        return cls(
            last_name=BasePersonName(last_name),
            first_name=BasePersonName(first_name),
        )


@dataclass(frozen=True, kw_only=True)
class PersonNameKana:
    """人名（カナ）を表す複合 Value Object"""

    last_name: BasePersonNameKana  # セイ（例: ヤマダ）
    first_name: BasePersonNameKana  # メイ（例: タロウ）

    def __post_init__(self) -> None:
        """姓と名がカナ用プリミティブで構成されていることを検証する。"""
        if not isinstance(self.last_name, BasePersonNameKana):
            raise DomainValidationError(
                "姓（カナ）は BasePersonNameKana で指定してください。"
            )
        if not isinstance(self.first_name, BasePersonNameKana):
            raise DomainValidationError(
                "名（カナ）は BasePersonNameKana で指定してください。"
            )

    @property
    def full_name(self) -> str:
        """フルネームカナを取得（スペース区切り）"""
        return f"{self.last_name.value} {self.first_name.value}"

    @classmethod
    def create(cls, *, last_name: str, first_name: str) -> Self:
        """未加工文字列から生成するファクトリ（半角カナも全角に自動補正）"""
        return cls(
            last_name=BasePersonNameKana(last_name),
            first_name=BasePersonNameKana(first_name),
        )


@dataclass(frozen=True, kw_only=True)
class PersonNames:
    """人名一式（漢字＋カナ）を束ねる複合 Value Object"""

    kanji: PersonName
    kana: PersonNameKana

    def __post_init__(self) -> None:
        """漢字氏名とカナ氏名が対応する Value Object であることを検証する。"""
        if not isinstance(self.kanji, PersonName):
            raise DomainValidationError("漢字氏名は PersonName で指定してください。")
        if not isinstance(self.kana, PersonNameKana):
            raise DomainValidationError(
                "カナ氏名は PersonNameKana で指定してください。"
            )

    @property
    def full_name(self) -> str:
        return self.kanji.full_name

    @property
    def full_name_kana(self) -> str:
        return self.kana.full_name

    @classmethod
    def create(
        cls,
        *,
        last_name: str,
        first_name: str,
        last_name_kana: str,
        first_name_kana: str,
    ) -> Self:
        """文字列から一括生成するファクトリ"""
        return cls(
            kanji=PersonName.create(last_name=last_name, first_name=first_name),
            kana=PersonNameKana.create(
                last_name=last_name_kana, first_name=first_name_kana
            ),
        )
