from __future__ import annotations

import pytest

from app.application.corporate import CorporateNotFoundError
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.store.exceptions import (
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)


@pytest.mark.parametrize(
    ("error_type", "expected_message"),
    [
        (DomainError, "ドメインエラーが発生しました。"),
        (
            DomainValidationError,
            "ドメインプリミティブに不正な値が指定されました。",
        ),
        (
            CorporateNameAlreadyExistsError,
            "同じ法人名の法人が既に登録されています。",
        ),
        (CorporateNotFoundError, "指定された法人が見つかりません。"),
        (StoreNotFoundError, "指定された店舗が見つかりません。"),
        (
            StoreNameAlreadyExistsError,
            "同一法人内に同じ店舗名の店舗が既に登録されています。",
        ),
        (
            StoreCodeAlreadyExistsError,
            "同一法人内に同じ店舗コードの店舗が既に登録されています。",
        ),
    ],
)
def test_domain_error_default_messages_are_japanese(
    error_type: type[Exception], expected_message: str
) -> None:
    # Arrange
    # Act
    actual = str(error_type())

    # Assert
    assert actual == expected_message
