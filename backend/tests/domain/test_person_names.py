"""人名プリミティブと Value Object のテスト。"""

from __future__ import annotations

from dataclasses import fields

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.person_name import (
    BasePersonNameKana,
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)


def test_person_name_create_normalizes_whitespace() -> None:
    # Arrange / Act
    actual = PersonName(
        last_name=PersonNamePart("  山田 "), first_name=PersonNamePart(" 太郎 ")
    )

    # Assert
    assert actual.full_name == "山田 太郎"


def test_person_name_kana_create_normalizes_half_width_kana() -> None:
    # Arrange / Act
    actual = PersonNameKana(
        last_name=PersonNameKanaPart("ｻﾝﾌﾟﾙ"), first_name=PersonNameKanaPart("ﾀﾛｳ")
    )

    # Assert
    assert actual.full_name == "サンプル タロウ"


@pytest.mark.parametrize("value", ["ヵ", "ヶ"])
def test_person_name_kana_accepts_small_katakana(value: str) -> None:
    # Arrange / Act
    actual = BasePersonNameKana(value)

    # Assert
    assert actual.value == value


@pytest.mark.parametrize("value", ["さんぷる", "Sample", "サンプル薬局"])
def test_person_name_kana_rejects_non_katakana(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        BasePersonNameKana(value)

    assert str(exc_info.value) == "氏名（カナ）は全角カタカナで入力してください。"


def test_person_name_rejects_raw_string_component() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        PersonName(
            last_name="山田",  # type: ignore[arg-type]
            first_name=PersonNamePart("太郎"),
        )

    assert str(exc_info.value) == "姓は PersonNamePart で指定してください。"


def test_person_name_kana_rejects_raw_string_component() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        PersonNameKana(
            last_name="ヤマダ",  # type: ignore[arg-type]
            first_name=PersonNameKanaPart("タロウ"),
        )

    assert str(exc_info.value) == "姓（カナ）は PersonNameKanaPart で指定してください。"


def test_person_names_rejects_raw_kanji_value_object() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        PersonNames(
            kanji="山田 太郎",  # type: ignore[arg-type]
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        )

    assert str(exc_info.value) == "漢字氏名は PersonName で指定してください。"


def test_person_names_rejects_raw_kana_value_object() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
            ),
            kana="ヤマダ タロウ",  # type: ignore[arg-type]
        )

    assert str(exc_info.value) == "カナ氏名は PersonNameKana で指定してください。"


def test_person_names_create_normalizes_all_name_parts() -> None:
    # Arrange / Act
    actual = PersonNames(
        kanji=PersonName(
            last_name=PersonNamePart(" 山田 "), first_name=PersonNamePart(" 太郎 ")
        ),
        kana=PersonNameKana(
            last_name=PersonNameKanaPart(" ｻﾝﾌﾟﾙ "),
            first_name=PersonNameKanaPart(" ﾀﾛｳ "),
        ),
    )

    # Assert
    assert actual.full_name == "山田 太郎"
    assert actual.full_name_kana == "サンプル タロウ"


def test_kana_pattern_is_not_an_instance_field() -> None:
    # Arrange / Act
    field_names = {field.name for field in fields(BasePersonNameKana)}

    # Assert
    assert field_names == {"value"}
