"""個人メールを必要としないログインIDの規則。"""

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import LoginId


def test_ログインID_大文字と前後空白がある場合_小文字へ正規化する() -> None:
    assert LoginId(" Staff.A-01_ ").value == "staff.a-01_"


@pytest.mark.parametrize(
    "raw", ["ab", "a" * 65, "@staff", "staff@example.com", "従業員", "a b"]
)
def test_ログインID_形式が不正な場合_拒否する(raw: str) -> None:
    with pytest.raises(DomainValidationError):
        LoginId(raw)


@pytest.mark.parametrize("raw", ["abc", "a" * 64])
def test_ログインID_許容する文字数の境界の場合_受理する(raw: str) -> None:
    assert LoginId(raw).value == raw
