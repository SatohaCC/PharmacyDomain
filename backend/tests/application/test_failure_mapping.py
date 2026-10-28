"""公開境界が業務分類と障害の区別を保つことを確認する。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from app.application.composition.errors import (
    ApplicationFailure,
    FailureKind,
    execution_scope,
    translate_errors,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.exceptions import StoreCodeAlreadyExistsError


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (DomainValidationError("不正な値です。"), FailureKind.INVALID_STATE),
        (StoreCodeAlreadyExistsError(), FailureKind.CONFLICT),
    ],
)
async def test_実行境界_業務例外は_分類と公開本文を維持して変換する(
    error: DomainValidationError | StoreCodeAlreadyExistsError, kind: FailureKind
) -> None:
    @translate_errors
    async def operation() -> None:
        raise error

    with pytest.raises(ApplicationFailure) as caught:
        await operation()

    assert caught.value.kind is kind
    assert caught.value.code == error.code
    assert caught.value.message == error.message
    assert caught.value.__cause__ is error


async def test_実行境界_未知の障害は_業務失敗へ変換しない() -> None:
    error = RuntimeError("想定外の障害です。")

    @translate_errors
    async def operation() -> None:
        raise error

    with pytest.raises(RuntimeError) as caught:
        await operation()

    assert caught.value is error


async def test_実行境界_正常な操作は_結果を変更しない() -> None:
    @translate_errors
    async def operation(value: int) -> int:
        return value

    assert await operation(42) == 42


async def test_確定境界_失敗時は_元の文脈を終了してから変換する() -> None:
    events: list[str] = []

    @asynccontextmanager
    async def scope() -> AsyncIterator[None]:
        try:
            yield
        finally:
            events.append("終了")

    with pytest.raises(ApplicationFailure):
        async with execution_scope(scope()):
            raise DomainValidationError()

    assert events == ["終了"]
