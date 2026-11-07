"""手入力用の法人コードの契約を確認する。"""

import pytest

from app.domain.corporate.primitives import CorporateLoginCode
from app.domain.foundation.exceptions import DomainValidationError


def test_法人コード_先頭がゼロでも_六桁を維持する() -> None:
    assert CorporateLoginCode("000012").value == "000012"


@pytest.mark.parametrize(
    "value", ["", "12345", "1234567", "１２３４５６", "abcdef", " 123456", "123456\n"]
)
def test_法人コード_半角数字六桁以外は_拒否する(value: str) -> None:
    with pytest.raises(DomainValidationError):
        CorporateLoginCode(value)
