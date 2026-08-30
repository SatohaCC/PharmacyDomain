"""例外とHTTPステータスの対応づけを、全例外クラスに対して固定する。

対応表は「足し忘れても誰も気づかない」場所である。新しい例外を作って表へ
入れ忘れると、未検出が404ではなく422で返り、クライアントの再試行判断が壊れる。
そこで表を1件ずつ確かめるのではなく、``app/domain`` と ``app/application`` に
定義された例外クラスを全部集めてから規則を当てる。
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from collections.abc import Iterator
from http import HTTPStatus
from types import ModuleType

import pytest

import app.application
import app.domain
from app.application.common.exceptions import ApplicationError, AuthorizationError
from app.application.store.exceptions import StoreNotFoundError
from app.domain.foundation.exceptions import DomainError, DomainValidationError
from app.domain.store.exceptions import StoreNameAlreadyExistsError
from app.presentational.errors import (
    TranslatableError,
    error_responses,
    status_for,
    status_for_type,
    to_response,
)
from app.presentational.exceptions import AuthenticationError, PresentationError

#: 名前に含まれると 409（既存のデータ・状態との衝突）を意味する語。
_CONFLICT_MARKERS = ("Already", "Conflict")


def _exception_classes(package: ModuleType) -> Iterator[type[BaseException]]:
    """パッケージ配下で定義された例外クラスを集める。"""
    prefix = f"{package.__name__}."
    for module_info in pkgutil.walk_packages(package.__path__, prefix):
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            if not isinstance(value, type) or not issubclass(value, BaseException):
                continue
            # 再エクスポートを二重に数えない。定義元のモジュールでだけ拾う。
            if value.__module__ != module_info.name:
                continue
            yield value


def _all_exception_classes() -> list[type[BaseException]]:
    return sorted(
        {*_exception_classes(app.domain), *_exception_classes(app.application)},
        key=lambda klass: f"{klass.__module__}.{klass.__qualname__}",
    )


def test_例外クラスの収集が_一定数以上を見つける() -> None:
    """走査が壊れたときに、無検査で緑になるのを防ぐ。"""
    # Act
    classes = _all_exception_classes()

    # Assert
    assert len(classes) > 50


def test_全ての例外が_翻訳対象の基底を継承している() -> None:
    """基底を外れた例外は翻訳器に届かず、素の500として漏れる。"""
    # Arrange
    classes = _all_exception_classes()

    # Act
    orphans = [
        f"{klass.__module__}.{klass.__qualname__}"
        for klass in classes
        if not issubclass(klass, DomainError | ApplicationError)
    ]

    # Assert
    assert not orphans, f"DomainError / ApplicationError を継承しない例外: {orphans}"


@pytest.mark.parametrize(
    "error_type",
    [
        pytest.param(klass, id=klass.__name__)
        for klass in _all_exception_classes()
        if klass.__name__.endswith("NotFoundError")
    ],
)
def test_未検出を表す例外は_404になる(error_type: type[TranslatableError]) -> None:
    # Act
    status = status_for_type(error_type)

    # Assert
    assert status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    "error_type",
    [
        pytest.param(klass, id=klass.__name__)
        for klass in _all_exception_classes()
        if not klass.__name__.endswith("NotFoundError")
        and any(marker in klass.__name__ for marker in _CONFLICT_MARKERS)
    ],
)
def test_衝突を表す例外は_409になる(error_type: type[TranslatableError]) -> None:
    # Act
    status = status_for_type(error_type)

    # Assert
    assert status == HTTPStatus.CONFLICT


def test_規則の対象となる例外が_両方とも存在する() -> None:
    """規則が1件も当たらないまま緑になるのを防ぐ。"""
    # Arrange
    names = [klass.__name__ for klass in _all_exception_classes()]

    # Assert
    assert any(name.endswith("NotFoundError") for name in names)
    assert any(marker in name for name in names for marker in _CONFLICT_MARKERS)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), HTTPStatus.UNAUTHORIZED),
        (AuthorizationError(), HTTPStatus.FORBIDDEN),
        (StoreNotFoundError(), HTTPStatus.NOT_FOUND),
        (StoreNameAlreadyExistsError(), HTTPStatus.CONFLICT),
        (DomainValidationError(), HTTPStatus.UNPROCESSABLE_CONTENT),
        (DomainError(), HTTPStatus.UNPROCESSABLE_CONTENT),
        (ApplicationError(), HTTPStatus.UNPROCESSABLE_CONTENT),
        (PresentationError(), HTTPStatus.BAD_REQUEST),
    ],
)
def test_代表的な例外が_想定のステータスへ対応づく(
    error: TranslatableError, expected: HTTPStatus
) -> None:
    # Act & Assert
    assert status_for(error) == expected


def test_応答本文は_共通の3項目だけを含む() -> None:
    """例外の型名やスタックを外へ出さない。"""
    # Arrange
    error = StoreNotFoundError("店舗が見つかりません。")

    # Act
    response = to_response(error)

    # Assert: ``errors`` は入力検証のときだけ埋まるが、キーは常に存在させる。
    assert response.status_code == int(HTTPStatus.NOT_FOUND)
    assert json.loads(bytes(response.body)) == {
        "code": "STORE_NOT_FOUND",
        "message": "店舗が見つかりません。",
        "errors": [],
    }


def test_返しうる全ステータスが_OpenAPIの説明を持つ() -> None:
    """説明の無いステータスを返すと、スキーマへ書けないエラーができる。"""
    # Arrange
    statuses = {
        status_for_type(klass)
        for klass in _all_exception_classes()
        if issubclass(klass, DomainError | ApplicationError)
    }
    statuses |= {status_for(AuthenticationError()), status_for(PresentationError())}

    # Act: 説明が無いステータスを渡すと KeyError で落ちる。
    documented = error_responses(*sorted(statuses))

    # Assert
    assert set(documented) == {int(status) for status in statuses}
