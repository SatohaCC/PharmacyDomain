"""法人（Corporate）の社会ルール適合性（法人番号、インボイス番号、法人格、住所、連絡先）に関するドメインテスト。"""

from __future__ import annotations

import pytest

from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateAddressLine,
    CorporateEmailAddress,
    CorporateName,
    CorporateNumber,
    CorporatePhoneNumber,
    CorporatePostalCode,
    CorporateType,
    InvoiceRegistrationNumber,
)
from app.domain.corporate.value_objects import (
    CorporateAddress,
    CorporateContactInfo,
    CorporateRepresentativeName,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.person_name import PersonNamePart


def _representative() -> CorporateRepresentativeName:
    return CorporateRepresentativeName(
        last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
    )


# --- 1. 国税庁法人番号 (CorporateNumber) のテスト ---


def test_法人番号_有効な13桁とチェックディジット_生成に成功する() -> None:
    # Arrange: 7123456789012 (基礎番号 123456789012 のチェックディジットは 7)
    valid_number = "7123456789012"

    # Act
    corp_number = CorporateNumber(valid_number)

    # Assert
    assert corp_number.value == "7123456789012"


def test_法人番号_全角数字とハイフン_半角13桁に正規化される() -> None:
    # Arrange: 全角数字や空白
    input_value = " ７１２３４５６７８９０１２ "

    # Act
    corp_number = CorporateNumber(input_value)

    # Assert
    assert corp_number.value == "7123456789012"


@pytest.mark.parametrize(
    ("invalid_value", "expected_message"),
    [
        ("", "法人番号は空にできません。"),
        ("123456789012", "法人番号は半角数字13桁で入力してください。"),
        ("12345678901234", "法人番号は半角数字13桁で入力してください。"),
        ("712345678901A", "法人番号は半角数字13桁で入力してください。"),
        ("1123456789012", "法人番号のチェックディジットが不正です。"),  # 正しいCDは 7
    ],
)
def test_法人番号_不正な値_エラーを送出する(
    invalid_value: str, expected_message: str
) -> None:
    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        CorporateNumber(invalid_value)
    assert expected_message in str(exc_info.value)


# --- 2. 適格請求書発行事業者登録番号 (InvoiceRegistrationNumber) のテスト ---


def test_インボイス番号_有効なTプラス13桁_生成に成功する() -> None:
    # Arrange
    value = "T7123456789012"

    # Act
    invoice = InvoiceRegistrationNumber(value)

    # Assert
    assert invoice.value == "T7123456789012"


def test_インボイス番号_小文字tや全角_正規化される() -> None:
    # Arrange
    value = " ｔ７１２３４５６７８９０１２ "

    # Act
    invoice = InvoiceRegistrationNumber(value)

    # Assert
    assert invoice.value == "T7123456789012"


@pytest.mark.parametrize(
    ("invalid_value", "expected_message"),
    [
        ("", "適格請求書発行事業者登録番号は空にできません。"),
        (
            "7123456789012",
            "適格請求書発行事業者登録番号は'T'で始まる半角英数字14桁で入力してください。",
        ),
        (
            "T12345678901",
            "適格請求書発行事業者登録番号は'T'で始まる半角英数字14桁で入力してください。",
        ),
        (
            "T12345678901234",
            "適格請求書発行事業者登録番号は'T'で始まる半角英数字14桁で入力してください。",
        ),
        (
            "A7123456789012",
            "適格請求書発行事業者登録番号は'T'で始まる半角英数字14桁で入力してください。",
        ),
    ],
)
def test_インボイス番号_不正な値_エラーを送出する(
    invalid_value: str, expected_message: str
) -> None:
    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        InvoiceRegistrationNumber(invalid_value)
    assert expected_message in str(exc_info.value)


# --- 3. 法人エンティティの社会ルール属性と不変条件テスト ---


def test_法人_法人格および法人番号とインボイス番号を設定_保持できる() -> None:
    # Arrange
    corp_number = CorporateNumber("7123456789012")
    invoice = InvoiceRegistrationNumber("T7123456789012")
    address = CorporateAddress(
        postal_code=CorporatePostalCode("100-0001"),
        address_line=CorporateAddressLine("東京都千代田区千代田1-1"),
    )
    contact = CorporateContactInfo(
        phone_number=CorporatePhoneNumber("03-1234-5678"),
        email=CorporateEmailAddress("contact@example.co.jp"),
    )

    # Act
    corporate = Corporate(
        id=CorporateId.generate(),
        name=CorporateName("株式会社 メディカル"),
        representative_name=_representative(),
        corporate_type=CorporateType.STOCK_COMPANY,
        corporate_number=corp_number,
        invoice_number=invoice,
        address=address,
        contact_info=contact,
    )

    # Assert
    assert corporate.corporate_type == CorporateType.STOCK_COMPANY
    assert corporate.corporate_number == corp_number
    assert corporate.invoice_number == invoice
    assert corporate.address == address
    assert corporate.contact_info == contact


def test_法人_法人番号とインボイス番号が不一致_エラーを送出する() -> None:
    # Arrange: 法人番号とインボイス番号の13桁部分が異なる
    corp_number = CorporateNumber("7123456789012")
    diff_invoice = InvoiceRegistrationNumber("T9999999999999")

    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        Corporate(
            id=CorporateId.generate(),
            name=CorporateName("株式会社 メディカル"),
            representative_name=_representative(),
            corporate_number=corp_number,
            invoice_number=diff_invoice,
        )
    assert "適格請求書発行事業者登録番号は法人番号と一致している必要があります" in str(
        exc_info.value
    )


def test_法人_各種変更メソッド_新しい不変インスタンスを返す() -> None:
    # Arrange
    corporate = Corporate(
        id=CorporateId.generate(),
        name=CorporateName("株式会社 メディカル"),
        representative_name=_representative(),
    )
    corp_number = CorporateNumber("7123456789012")
    invoice = InvoiceRegistrationNumber("T7123456789012")
    address = CorporateAddress(
        postal_code=CorporatePostalCode("100-0001"),
        address_line=CorporateAddressLine("東京都千代田区千代田1-1"),
    )
    contact = CorporateContactInfo(
        phone_number=CorporatePhoneNumber("03-1234-5678"),
    )

    # Act
    updated = (
        corporate.change_corporate_type(CorporateType.MEDICAL_CORPORATION)
        .update_corporate_number(corp_number)
        .update_invoice_number(invoice)
        .change_address(address)
        .change_contact_info(contact)
    )

    # Assert
    assert updated.corporate_type == CorporateType.MEDICAL_CORPORATION
    assert updated.corporate_number == corp_number
    assert updated.invoice_number == invoice
    assert updated.address == address
    assert updated.contact_info == contact
    # 元のインスタンスは不変
    assert corporate.corporate_type == CorporateType.STOCK_COMPANY
    assert corporate.corporate_number is None
