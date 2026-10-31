"""法人内ユーザーのメールアドレス値オブジェクトのテスト（TC-026, TC-027）。"""

from __future__ import annotations

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import CorporateUserEmail


def test_TC026_メールアドレスの前後の空白除去と小文字化正規化() -> None:
    # Arrange & Act
    email = CorporateUserEmail("  Test.User@example.test  ")

    # Assert
    assert email.value == "test.user@example.test"


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        "invalid-email",
        "test user@example.test",
        "@example.test",
        "test@",
        "test@example",
    ],
    ids=[
        "空",
        "空白のみ",
        "@なし",
        "空白混入",
        "ローカル部なし",
        "ドメイン部なし",
        "TLDなし",
    ],
)
def test_TC027_不正なメールアドレス形式をDomainValidationErrorで拒否する(
    invalid_input: str,
) -> None:
    with pytest.raises(DomainValidationError):
        CorporateUserEmail(invalid_input)
