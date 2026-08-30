"""複数コンテキストで共有する人名語彙（Shared Kernel）。"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString
from app.domain.foundation.value_object import ValueObject


@dataclass(frozen=True)
class BasePersonName(BaseNormalizedString):
    """人名（漢字・アルファベット等）の基底プリミティブ。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("氏名は空にできません。")
        if len(self.value) > 50:
            raise DomainValidationError("氏名は50文字以内で入力してください。")


@dataclass(frozen=True)
class BasePersonNameKana(BaseNormalizedString):
    """人名（フリガナ・全角カタカナ）の基底プリミティブ。

    空白の正規化に加え、NFKCにより半角カナを全角カタカナへ変換します。
    """

    # 全角カタカナ（小書き・ヵ・ヶを含む）、長音符(ー)、中黒(・)、スペースを許容する正規表現
    KANA_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[ァ-ヶー・\s]+$")

    def _normalize(self, value: str) -> str:
        normalized = super()._normalize(value)
        return unicodedata.normalize("NFKC", normalized)

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("氏名（カナ）は空にできません。")
        if len(self.value) > 50:
            raise DomainValidationError("氏名（カナ）は50文字以内で入力してください。")
        if not self.KANA_PATTERN.fullmatch(self.value):
            raise DomainValidationError(
                "氏名（カナ）は全角カタカナで入力してください。"
            )


class PersonNamePart(BasePersonName):
    """姓または名として保持する具象プリミティブ。"""


class PersonNameKanaPart(BasePersonNameKana):
    """姓または名のフリガナとして保持する具象プリミティブ。"""


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
