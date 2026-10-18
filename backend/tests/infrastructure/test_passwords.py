"""パスワードの平文保持と曖昧な正規化を防ぐ。"""

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.infrastructure.identity.passwords import hash_password, verify_password


def test_パスワード_同じ平文でも異なるソルトで照合できる() -> None:
    # Arrange
    password = "テスト用の長いパスフレーズ12345"
    # Act
    first, second = hash_password(password), hash_password(password)
    # Assert
    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password(password + "x", first)
    assert not verify_password(" " + password, first)


@pytest.mark.parametrize("password", ["", "短いパスワード", "a" * 129])
def test_パスワード_不正な長さを保存前に拒否する(password: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        hash_password(password)
