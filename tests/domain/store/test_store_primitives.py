"""店舗コンテキストのドメインプリミティブ・値オブジェクトのテスト。"""

from __future__ import annotations

import uuid

import pytest

from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate import CorporateId
from app.domain.store import (
    ContactInfo,
    InsurancePharmacyNumber,
    StoreAddress,
    StoreAddressLine,
    StoreCode,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreId,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
)


def test_store_id_generates_uuid7() -> None:
    # Arrange / Act
    store_id = StoreId.generate()

    # Assert
    assert store_id.value.version == 7


def test_store_id_parse_rejects_non_uuid_string() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        StoreId.parse("not-a-uuid")


def test_store_id_rejects_uuid4() -> None:
    # Arrange: UUIDとしては正しいがv7ではない値
    uuid4_value = uuid.uuid4()

    # Act / Assert
    with pytest.raises(DomainValidationError):
        StoreId(uuid4_value)


def test_store_name_collapses_whitespace() -> None:
    # Arrange / Act
    actual = StoreName("  サンプル   薬局  ")

    # Assert
    assert actual.value == "サンプル 薬局"


@pytest.mark.parametrize(
    ("value", "expected_message"),
    [
        ("", "店舗名は空にできません。"),
        ("   ", "店舗名は空にできません。"),
        ("あ" * 101, "店舗名は100文字以内で指定してください。"),
    ],
)
def test_store_name_rejects_invalid_values(value: str, expected_message: str) -> None:
    # Arrange: value は parametrize から与えられる
    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        StoreName(value)

    assert str(exc_info.value) == expected_message


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # 小書きの「ァ」(U+30A1) は「ア」(U+30A2) より手前にあるため、範囲指定を
        # 誤ると薬局名に頻出する「ファーマシー」が丸ごと弾かれる。回帰テストとして残す。
        ("ファーマシーサンプル", "ファーマシーサンプル"),
        ("サンプルファーマシーズ", "サンプルファーマシーズ"),
        ("ヴィレッジヤッキョク", "ヴィレッジヤッキョク"),
        ("チュウオウ・キタヤッキョク", "チュウオウ・キタヤッキョク"),  # 中黒
        ("サンプルヤッキョクー", "サンプルヤッキョクー"),  # 長音
        ("サンプル ヤッキョク", "サンプル ヤッキョク"),  # 半角スペース区切り
        ("サンプル　ヤッキョク", "サンプル ヤッキョク"),  # 全角スペースは半角へ正規化
    ],
)
def test_store_name_kana_accepts_katakana_forms(value: str, expected: str) -> None:
    # Arrange / Act
    actual = StoreNameKana(value)

    # Assert
    assert actual.value == expected


@pytest.mark.parametrize(
    "value",
    [
        "さんぷるやっきょく",  # ひらがな
        "サンプル薬局",  # 漢字混在
        "Sample Pharmacy",  # 半角英字
        "ｻﾝﾌﾟﾙﾔｯｷｮｸ",  # 半角カナ
    ],
)
def test_store_name_kana_rejects_non_katakana(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        StoreNameKana(value)

    assert str(exc_info.value) == "店舗名（カナ）は全角カタカナで入力してください。"


def test_store_name_kana_rejects_empty_value() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        StoreNameKana("   ")

    assert str(exc_info.value) == "店舗名（カナ）は空にできません。"


@pytest.mark.parametrize("value", ["Sample Pharmacy", "ST-001_A", "A.B,C&D'E"])
def test_store_name_romaji_accepts_ascii_forms(value: str) -> None:
    # Arrange / Act
    actual = StoreNameRomaji(value)

    # Assert
    assert actual.value == value


def test_store_name_romaji_rejects_japanese() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        StoreNameRomaji("サンプル")


@pytest.mark.parametrize(
    ("value", "expected_message"),
    [
        ("   ", "店舗コードは空にできません。"),
        ("X" * 21, "店舗コードは20文字以内で指定してください。"),
    ],
)
def test_store_code_rejects_invalid_values(value: str, expected_message: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        StoreCode(value)

    assert str(exc_info.value) == expected_message


def test_insurance_pharmacy_number_accepts_valid_number() -> None:
    # Arrange / Act
    actual = InsurancePharmacyNumber("1341234567")

    # Assert
    assert actual.value == "1341234567"


@pytest.mark.parametrize(
    ("value", "expected_message"),
    [
        ("134123456", "保険薬局指定番号は半角数字10桁で入力してください。"),
        ("13412345678", "保険薬局指定番号は半角数字10桁で入力してください。"),
        ("13A1234567", "保険薬局指定番号は半角数字10桁で入力してください。"),
        ("0041234567", "保険薬局指定番号の都道府県コード（上2桁）が不正です。"),
        ("4841234567", "保険薬局指定番号の都道府県コード（上2桁）が不正です。"),
        (
            "1311234567",
            "保険薬局指定番号の3桁目（調剤区分）は '4' である必要があります。",
        ),
    ],
)
def test_insurance_pharmacy_number_rejects_invalid_values(
    value: str, expected_message: str
) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        InsurancePharmacyNumber(value)

    assert str(exc_info.value) == expected_message


def test_store_names_rejects_raw_string_for_name() -> None:
    # Arrange / Act / Assert: 値オブジェクトを迂回した生文字列を拒否する
    with pytest.raises(DomainValidationError):
        StoreNames(
            name="サンプル薬局",  # type: ignore[arg-type]
            kana=StoreNameKana("サンプルヤッキョク"),
        )


def test_store_names_allows_omitting_romaji() -> None:
    # Arrange / Act
    actual = StoreNames(
        name=StoreName("サンプル薬局"),
        kana=StoreNameKana("サンプルヤッキョク"),
    )

    # Assert
    assert actual.romaji is None


def test_store_address_normalizes_postal_code() -> None:
    # Arrange / Act
    actual = StoreAddress(
        postal_code=StorePostalCode("1234567"),
        address=StoreAddressLine("東京都千代田区1-2-3"),
    )

    # Assert
    assert actual.postal_code.value == "123-4567"


def test_store_address_rejects_raw_string_for_address() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        StoreAddress(
            postal_code=StorePostalCode("1234567"),
            address="東京都千代田区1-2-3",  # type: ignore[arg-type]
        )


def test_contact_info_create_normalizes_blank_optional_values_to_none() -> None:
    # Arrange / Act
    actual = ContactInfo.create(
        phone_number=StorePhoneNumber("03-1234-5678"),
        fax_number=StoreFaxNumber(""),
        email=None,
    )

    # Assert
    assert actual.phone_number.value == "0312345678"
    assert actual.fax_number is None
    assert actual.email is None


def test_contact_info_keeps_optional_values_when_supplied() -> None:
    # Arrange / Act
    actual = ContactInfo.create(
        phone_number=StorePhoneNumber("0312345678"),
        fax_number=StoreFaxNumber("0312345679"),
        email=StoreEmailAddress("Info@Example.COM"),
    )

    # Assert
    assert actual.fax_number is not None
    assert actual.fax_number.value == "0312345679"
    assert actual.email is not None
    assert actual.email.value == "info@example.com"


def test_contact_info_requires_phone_number() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        ContactInfo.create(phone_number=StorePhoneNumber(""))

    assert str(exc_info.value) == "電話番号は空にできません。"


def test_contact_info_rejects_fax_number_passed_as_phone_number() -> None:
    # Arrange: TELとFAXは別型なので、取り違えは実行時にも落ちる
    fax = StoreFaxNumber("0312345679")

    # Act
    with pytest.raises(DomainValidationError) as exc_info:
        ContactInfo.create(phone_number=fax)  # type: ignore[arg-type]

    # Assert
    assert str(exc_info.value) == "電話番号は StorePhoneNumber で指定してください。"


@pytest.mark.parametrize(
    ("factory", "expected_message"),
    [
        (
            StorePhoneNumber,
            "電話番号は0で始まる10桁または11桁の数字である必要があります。",
        ),
        (
            StoreFaxNumber,
            "FAX番号は0で始まる10桁または11桁の数字である必要があります。",
        ),
    ],
)
def test_telephone_messages_name_the_field_in_japanese(
    factory: type[StorePhoneNumber | StoreFaxNumber], expected_message: str
) -> None:
    # Arrange: 内部クラス名ではなく利用者に意味の通る項目名が出ること。
    # TELとFAXが同じ文言にならないことも同時に確認する。
    # Act
    with pytest.raises(DomainValidationError) as exc_info:
        factory("12345")

    # Assert
    assert str(exc_info.value) == expected_message


def test_email_message_names_the_field_in_japanese() -> None:
    # Arrange / Act
    with pytest.raises(DomainValidationError) as exc_info:
        StoreEmailAddress("bad-address")

    # Assert
    assert str(exc_info.value) == "メールアドレスの形式が不正です。"


def test_store_id_message_names_the_field_in_japanese() -> None:
    # Arrange / Act
    with pytest.raises(DomainValidationError) as exc_info:
        StoreId.parse("not-a-uuid")

    # Assert
    assert str(exc_info.value).startswith(
        "店舗IDはUUID形式の文字列である必要があります。"
    )


def test_store_id_differs_from_other_id_type_with_same_uuid() -> None:
    # Arrange: 同じUUIDでも型が違えば別物として扱われることを確認する
    raw = uuid.uuid7()

    # Act
    store_id = StoreId(raw)
    corporate_id = CorporateId(raw)

    # Assert: mypy も非重複比較として警告する（型レベルでの分離が効いている証跡）が、
    # 実行時にも取り違えが等価にならないことを保証しておく。
    assert store_id != corporate_id  # type: ignore[comparison-overlap]
