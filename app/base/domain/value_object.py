"""コンテキスト横断で使う複合 Value Object。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from app.base.domain.field_guard import ensure_declared_field_types
from app.base.domain.primitives.person_primitives import (
    PersonNameKanaPart,
    PersonNamePart,
)


@dataclass(frozen=True, kw_only=True)
class ValueObject:
    """複合 Value Object の初期化順序を統一する基底クラス。"""

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {}

    def __post_init__(self) -> None:
        """正規化、宣言型の照合、業務ルール検証を順に実行する。"""
        self._normalize_fields()
        ensure_declared_field_types(self, labels=self._FIELD_LABELS)
        self.validate()

    def _normalize_fields(self) -> None:
        """派生クラスが複合フィールドを正規化するためのフック。"""
        return None

    def validate(self) -> None:
        """派生クラスが値オブジェクト固有の不変条件を検証するためのフック。"""
        return None


@dataclass(frozen=True, kw_only=True)
class PersonName(ValueObject):
    """人名（漢字）を表す複合 Value Object。"""

    last_name: PersonNamePart
    first_name: PersonNamePart

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "last_name": "姓",
        "first_name": "名",
    }

    @property
    def full_name(self) -> str:
        """フルネームをスペース区切りで返す。"""
        return f"{self.last_name.value} {self.first_name.value}"

    @classmethod
    def create(cls, *, last_name: str, first_name: str) -> Self:
        """未加工文字列から生成する。"""
        return cls(
            last_name=PersonNamePart(last_name),
            first_name=PersonNamePart(first_name),
        )


@dataclass(frozen=True, kw_only=True)
class PersonNameKana(ValueObject):
    """人名（カナ）を表す複合 Value Object。"""

    last_name: PersonNameKanaPart
    first_name: PersonNameKanaPart

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "last_name": "姓（カナ）",
        "first_name": "名（カナ）",
    }

    @property
    def full_name(self) -> str:
        """フルネームカナをスペース区切りで返す。"""
        return f"{self.last_name.value} {self.first_name.value}"

    @classmethod
    def create(cls, *, last_name: str, first_name: str) -> Self:
        """未加工文字列から生成する。"""
        return cls(
            last_name=PersonNameKanaPart(last_name),
            first_name=PersonNameKanaPart(first_name),
        )


@dataclass(frozen=True, kw_only=True)
class PersonNames(ValueObject):
    """人名一式（漢字とカナ）を束ねる複合 Value Object。"""

    kanji: PersonName
    kana: PersonNameKana

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "kanji": "漢字氏名",
        "kana": "カナ氏名",
    }

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
        """文字列から一括生成する。"""
        return cls(
            kanji=PersonName.create(last_name=last_name, first_name=first_name),
            kana=PersonNameKana.create(
                last_name=last_name_kana,
                first_name=first_name_kana,
            ),
        )
